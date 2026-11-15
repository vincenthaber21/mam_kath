import io
import json
from unittest import mock

import numpy as np
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from registry.models import MLModel

from . import services
from .models import Classification


def image_bytes(fmt="JPEG", color=(200, 40, 20), size=(64, 48)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


def fake_keras(meta, img):
    """Tiny dummy model: always 'fire' with 0.80."""
    return np.array([0.80, 0.05, 0.05, 0.05, 0.05]), 12.3


class Base(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("reviewer@example.com", "pass-1234-word", name="Reviewer")
        self.client.force_login(self.user)


@override_settings(EIC_DEMO_MODE=False, MEDIA_ROOT="/tmp/eic-test-media")
class ClassifyTests(Base):
    def setUp(self):
        super().setUp()
        self.model = MLModel.objects.create(
            name="EfficientNet-B0", preprocessing="efficientnet", is_active=True,
            labels_json=["fire", "crime", "medical_emergency", "accident", "disaster"],
            file=SimpleUploadedFile("m.keras", b"x"),
        )

    def post(self, data, name="a.jpg", reference=""):
        return self.client.post(reverse("classify"), {"image": SimpleUploadedFile(name, data), "reference_label": reference})

    @mock.patch.object(services, "_keras_predict", side_effect=fake_keras)
    def test_classify_saves_prediction(self, _):
        res = self.post(image_bytes(), reference="fire")
        rec = Classification.objects.get()
        self.assertRedirects(res, reverse("result", args=[rec.pk]))
        self.assertEqual(rec.status, "success")
        self.assertEqual(rec.predicted_label, "fire")
        self.assertAlmostEqual(rec.confidence, 0.80)
        self.assertFalse(rec.low_confidence)
        self.assertEqual((rec.width, rec.height), (64, 48))
        self.assertEqual(rec.model, self.model)
        self.assertTrue(rec.is_match)

    @mock.patch.object(services, "_keras_predict", return_value=(np.array([0.55, 0.15, 0.1, 0.1, 0.1]), 5.0))
    def test_below_60_percent_is_low_confidence(self, _):
        self.post(image_bytes())
        self.assertTrue(Classification.objects.get().low_confidence)

    def test_gif_is_rejected_and_logged_as_failed(self):
        self.post(image_bytes("GIF"), name="a.gif")
        rec = Classification.objects.get()
        self.assertEqual(rec.status, "failed")
        self.assertIn("JPG or PNG", rec.error)

    def test_corrupt_file_is_logged_as_failed(self):
        self.post(b"not an image at all", name="a.jpg")
        self.assertEqual(Classification.objects.get().status, "failed")

    def test_over_10_mb_is_rejected(self):
        self.post(b"0" * (10 * 1024 * 1024 + 1), name="big.jpg")
        rec = Classification.objects.get()
        self.assertEqual(rec.status, "failed")
        self.assertIn("maximum is 10 MB", rec.error)

    def test_no_active_model_without_demo_mode_fails(self):
        MLModel.objects.update(is_active=False)
        self.post(image_bytes())
        self.assertIn("No active model", Classification.objects.get().error)

    @mock.patch.object(services, "_keras_predict", side_effect=RuntimeError("boom"))
    def test_inference_crash_is_logged(self, _):
        self.post(image_bytes())
        rec = Classification.objects.get()
        self.assertEqual(rec.status, "failed")
        self.assertIn("boom", rec.error)

    def test_login_required(self):
        self.client.logout()
        res = self.client.get(reverse("classify"))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("login"), res["Location"])


@override_settings(EIC_DEMO_MODE=True, MEDIA_ROOT="/tmp/eic-test-media")
class DemoAndLogTests(Base):
    def test_demo_mode_classifies_without_model(self):
        self.client.post(reverse("classify"), {"image": SimpleUploadedFile("a.png", image_bytes("PNG"))})
        rec = Classification.objects.get()
        self.assertEqual(rec.status, "success")
        self.assertTrue(rec.demo)
        self.assertAlmostEqual(sum(rec.scores.values()), 1.0, places=3)

    def test_verification_incorrect_requires_actual_label(self):
        rec = Classification.objects.create(predicted_label="fire", confidence=0.9, scores={"fire": 0.9})
        res = self.client.post(reverse("result", args=[rec.pk]), {"verification": "incorrect", "actual_label": ""})
        self.assertEqual(res.status_code, 200)
        rec.refresh_from_db()
        self.assertEqual(rec.verification, "")
        self.client.post(reverse("result", args=[rec.pk]), {"verification": "incorrect", "actual_label": "accident"})
        rec.refresh_from_db()
        self.assertEqual((rec.verification, rec.actual_label), ("incorrect", "accident"))

    def test_verification_correct_copies_prediction(self):
        rec = Classification.objects.create(predicted_label="crime", confidence=0.9)
        self.client.post(reverse("result", args=[rec.pk]), {"verification": "correct"})
        rec.refresh_from_db()
        self.assertEqual(rec.actual_label, "crime")

    def test_history_filters_paginate_and_export(self):
        for i in range(25):
            Classification.objects.create(predicted_label="fire" if i % 2 else "crime", confidence=0.7, filename=f"img{i}.jpg")
        Classification.objects.create(status="failed", error="bad", filename="broken.jpg")
        res = self.client.get(reverse("history"))
        self.assertEqual(len(res.context["page"].object_list), 20)
        res = self.client.get(reverse("history"), {"predicted": "fire"})
        self.assertEqual(res.context["page"].paginator.count, 12)
        res = self.client.get(reverse("history"), {"status": "failed"})
        self.assertEqual(res.context["page"].paginator.count, 1)
        csv_text = self.client.get(reverse("history_export"), {"predicted": "crime"}).content.decode()
        self.assertEqual(len(csv_text.strip().splitlines()), 1 + 13)
