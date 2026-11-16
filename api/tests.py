import io
import json
from unittest import mock

import numpy as np
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from classifier import services
from classifier.models import Classification
from registry.models import MLModel

from .models import AuthToken


def image_bytes(fmt="JPEG", color=(200, 40, 20), size=(64, 48)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


def fake_keras(meta, img):
    return np.array([0.80, 0.05, 0.05, 0.05, 0.05]), 12.3


@override_settings(EIC_DEMO_MODE=False, MEDIA_ROOT="/tmp/eic-api-test-media")
class ApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "reporter@example.com", "pass-1234-word", name="Reporter"
        )
        self.model = MLModel.objects.create(
            name="EfficientNet-B0",
            preprocessing="efficientnet",
            is_active=True,
            labels_json=["fire", "crime", "medical_emergency", "accident", "disaster"],
            file=SimpleUploadedFile("m.keras", b"x"),
        )

    def login_token(self):
        res = self.client.post(
            reverse("api_login"),
            data=json.dumps({"email": "reporter@example.com", "password": "pass-1234-word"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        return res.json()["token"]

    def auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_health_is_public(self):
        res = self.client.get(reverse("api_health"))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

    def test_login_and_me(self):
        token = self.login_token()
        res = self.client.get(reverse("api_me"), **self.auth(token))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["email"], "reporter@example.com")

    def test_login_rejects_bad_password(self):
        res = self.client.post(
            reverse("api_login"),
            data=json.dumps({"email": "reporter@example.com", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 401)

    def test_classify_requires_image(self):
        res = self.client.post(reverse("api_classify"))
        self.assertEqual(res.status_code, 400)

    @mock.patch.object(services, "_keras_predict", side_effect=fake_keras)
    def test_classify_allows_guest(self, _):
        res = self.client.post(
            reverse("api_classify"),
            {"image": SimpleUploadedFile("fire.jpg", image_bytes(), content_type="image/jpeg")},
        )
        self.assertEqual(res.status_code, 201)
        rec = Classification.objects.get()
        self.assertIsNone(rec.user)
        self.assertEqual(rec.source, "mobile")

    @mock.patch.object(services, "_keras_predict", side_effect=fake_keras)
    def test_classify_from_mobile(self, _):
        token = self.login_token()
        res = self.client.post(
            reverse("api_classify"),
            {
                "image": SimpleUploadedFile("fire.jpg", image_bytes(), content_type="image/jpeg"),
                "notes": "Smoke near the market",
                "location_text": "Santa Maria plaza",
                "latitude": "17.357",
                "longitude": "120.496",
            },
            **self.auth(token),
        )
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(body["predicted_label"], "fire")
        self.assertEqual(body["source"], "mobile")
        self.assertEqual(body["notes"], "Smoke near the market")
        self.assertAlmostEqual(body["latitude"], 17.357)
        rec = Classification.objects.get()
        self.assertEqual(rec.user, self.user)
        self.assertEqual(rec.source, "mobile")

    @mock.patch.object(services, "_keras_predict", side_effect=fake_keras)
    def test_verify_and_list(self, _):
        token = self.login_token()
        create = self.client.post(
            reverse("api_classify"),
            {"image": SimpleUploadedFile("a.jpg", image_bytes(), content_type="image/jpeg")},
            **self.auth(token),
        )
        pk = create.json()["id"]
        verify = self.client.post(
            reverse("api_classification_verify", args=[pk]),
            data=json.dumps({"verification": "correct"}),
            content_type="application/json",
            **self.auth(token),
        )
        self.assertEqual(verify.status_code, 200)
        self.assertEqual(verify.json()["verification"], "correct")
        listing = self.client.get(reverse("api_classifications"), **self.auth(token))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)

    def test_logout_revokes_token(self):
        token = self.login_token()
        self.assertTrue(AuthToken.objects.filter(key=token).exists())
        res = self.client.post(reverse("api_logout"), **self.auth(token))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(AuthToken.objects.filter(key=token).exists())
        me = self.client.get(reverse("api_me"), **self.auth(token))
        self.assertEqual(me.status_code, 401)
