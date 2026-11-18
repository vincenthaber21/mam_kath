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
            "reporter@example.com",
            "pass-1234-word",
            username="reporter",
            name="Reporter",
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

    def auth_header_token(self, token):
        """Mobile clients send X-EIC-Token so Dev Tunnels ignore app credentials."""
        return {"HTTP_X_EIC_TOKEN": token}

    def test_api_index_is_public(self):
        res = self.client.get(reverse("api_index"))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        self.assertEqual(res.json()["health"], "/api/health/")

    def test_health_is_public(self):
        res = self.client.get(reverse("api_health"))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

    def test_login_and_me(self):
        token = self.login_token()
        res = self.client.get(reverse("api_me"), **self.auth(token))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["email"], "reporter@example.com")

    def test_me_accepts_x_eic_token(self):
        token = self.login_token()
        res = self.client.get(reverse("api_me"), **self.auth_header_token(token))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["email"], "reporter@example.com")

    def test_login_rejects_bad_password(self):
        res = self.client.post(
            reverse("api_login"),
            data=json.dumps({"email": "reporter@example.com", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 401)

    def test_login_accepts_username(self):
        res = self.client.post(
            reverse("api_login"),
            data=json.dumps({"username": "reporter", "password": "pass-1234-word"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["username"], "reporter")
        self.assertTrue(res.json()["token"])

    def test_register_resident_from_santa_maria(self):
        res = self.client.post(
            reverse("api_register"),
            data=json.dumps({
                "username": "juan.delacruz",
                "email": "juan@example.com",
                "first_name": "Juan",
                "middle_name": "Santos",
                "last_name": "Dela Cruz",
                "phone": "09171234567",
                "barangay": "Suso",
                "password": "pass-1234-word",
                "password_confirm": "pass-1234-word",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertTrue(body["token"])
        self.assertEqual(body["user"]["email"], "juan@example.com")
        self.assertEqual(body["user"]["username"], "juan.delacruz")
        self.assertEqual(body["user"]["role"], "resident")
        self.assertEqual(body["user"]["barangay"], "Suso")
        self.assertEqual(body["user"]["name"], "Juan Santos Dela Cruz")
        user = get_user_model().objects.get(email="juan@example.com")
        self.assertEqual(user.role, get_user_model().Role.RESIDENT)
        self.assertTrue(user.check_password("pass-1234-word"))

    def test_register_requires_santa_maria_barangay(self):
        res = self.client.post(
            reverse("api_register"),
            data=json.dumps({
                "username": "maria.reyes",
                "email": "maria@example.com",
                "first_name": "Maria",
                "last_name": "Reyes",
                "barangay": "Not A Real Barangay",
                "password": "pass-1234-word",
                "password_confirm": "pass-1234-word",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("barangay", res.json()["fields"])

    def test_register_rejects_duplicate_email(self):
        res = self.client.post(
            reverse("api_register"),
            data=json.dumps({
                "username": "another.user",
                "email": "reporter@example.com",
                "first_name": "Ann",
                "last_name": "Other",
                "barangay": "Suso",
                "password": "pass-1234-word",
                "password_confirm": "pass-1234-word",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.json()["fields"])

    def test_register_rejects_password_mismatch(self):
        res = self.client.post(
            reverse("api_register"),
            data=json.dumps({
                "username": "new.resident",
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "Resident",
                "barangay": "Suso",
                "password": "pass-1234-word",
                "password_confirm": "different-password",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("password_confirm", res.json()["fields"])

    def test_register_always_creates_resident_role(self):
        """Clients cannot self-register as officer/admin via the API."""
        res = self.client.post(
            reverse("api_register"),
            data=json.dumps({
                "username": "sneaky.admin",
                "email": "sneaky@example.com",
                "first_name": "Sneaky",
                "last_name": "Admin",
                "barangay": "Suso",
                "password": "pass-1234-word",
                "password_confirm": "pass-1234-word",
                "role": "admin",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["user"]["role"], "resident")

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
                "location_text": "Suso",
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
        self.assertEqual(body["location_text"], "Suso")
        self.assertAlmostEqual(body["latitude"], 17.357)
        rec = Classification.objects.get()
        self.assertEqual(rec.user, self.user)
        self.assertEqual(rec.source, "mobile")
        self.assertEqual(rec.location_text, "Suso")

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
