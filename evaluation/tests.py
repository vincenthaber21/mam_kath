import io
import zipfile
from unittest import mock

import numpy as np
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from classifier import services
from registry.models import MLModel

from . import metrics
from .models import Evaluation


class MetricsTests(SimpleTestCase):
    def test_known_values(self):
        y_true = ["fire", "fire", "crime", "crime", "accident"]
        y_pred = ["fire", "crime", "crime", "crime", "accident"]
        m = metrics.compute(y_true, y_pred)
        self.assertAlmostEqual(m["accuracy"], 0.8)
        fire = next(c for c in m["per_class"] if c["label"] == "fire")
        crime = next(c for c in m["per_class"] if c["label"] == "crime")
        self.assertEqual((fire["precision"], fire["recall"], fire["support"]), (1.0, 0.5, 2))
        self.assertAlmostEqual(crime["precision"], 0.6667)
        self.assertEqual(m["confusion_matrix"][0], [1, 1, 0, 0, 0])  # actual fire row
        self.assertEqual(len(m["confusion_matrix"]), 5)

    def test_empty(self):
        self.assertEqual(metrics.compute([], [])["accuracy"], 0.0)

    def test_timing(self):
        self.assertEqual(metrics.timing([10, 20, 60]), {"mean": 30.0, "median": 20.0, "min": 10.0, "max": 60.0})


def jpeg(color):
    b = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(b, format="JPEG")
    return b.getvalue()


def predict_by_color(meta, img):
    r, g, b = img.convert("RGB").getpixel((5, 5))
    probs = np.array([0.9, 0.025, 0.025, 0.025, 0.025]) if r > 128 else np.array([0.025, 0.9, 0.025, 0.025, 0.025])
    return probs, 10.0


@override_settings(EVALUATION_SYNC=True, EIC_DEMO_MODE=False, MEDIA_ROOT="/tmp/eic-test-media")
class EvaluationRunTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("r@example.com", "pass-1234-word")
        self.client.force_login(self.user)
        self.model = MLModel.objects.create(
            name="M", is_active=True, labels_json=["fire", "crime", "medical_emergency", "accident", "disaster"],
            file=SimpleUploadedFile("m.keras", b"x"),
        )

    @mock.patch.object(services, "_keras_predict", side_effect=predict_by_color)
    def test_zip_is_evaluated(self, _):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("testset/fire/a.jpg", jpeg((250, 0, 0)))
            z.writestr("testset/fire/b.jpg", jpeg((0, 0, 250)))   # will be predicted crime
            z.writestr("testset/crime/c.jpg", jpeg((0, 0, 250)))
            z.writestr("testset/crime/broken.jpg", b"garbage")      # failed attempt
            z.writestr("testset/readme.txt", "ignored")
        res = self.client.post(reverse("evaluation"), {
            "test_set": SimpleUploadedFile("t.zip", buf.getvalue()), "model": self.model.pk, "update_model_metrics": "on",
        })
        ev = Evaluation.objects.get()
        self.assertRedirects(res, ev.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(ev.status, "done", ev.error)
        self.assertEqual((ev.total, ev.processed, ev.failed), (4, 4, 1))
        self.assertAlmostEqual(ev.accuracy, 0.6667)
        self.assertEqual(ev.misclassified.count(), 1)
        self.model.refresh_from_db()
        self.assertAlmostEqual(self.model.test_accuracy, 0.6667)
        page = self.client.get(ev.get_absolute_url())
        self.assertContains(page, "Confusion matrix")
        self.assertEqual(self.client.get(reverse("evaluation_csv", args=[ev.pk])).status_code, 200)

    def test_rejects_non_zip(self):
        res = self.client.post(reverse("evaluation"), {"test_set": SimpleUploadedFile("t.txt", b"x"), "model": self.model.pk})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Evaluation.objects.exists())
