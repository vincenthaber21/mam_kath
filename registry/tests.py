from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import MLModel, TrainingRun


class RegistryTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("r@example.com", "pass-1234-word"))

    def test_only_one_active_model(self):
        a = MLModel.objects.create(name="A", is_active=True)
        b = MLModel.objects.create(name="B")
        self.client.post(reverse("model_activate", args=[b.pk]))
        a.refresh_from_db(); b.refresh_from_db()
        self.assertFalse(a.is_active)
        self.assertTrue(b.is_active)

    def test_seed_demo_and_pages_render(self):
        call_command("seed_demo", verbosity=0)
        self.assertEqual(MLModel.objects.count(), 3)
        for name in ("classify", "history", "evaluation", "models", "dataset"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertContains(self.client.get(reverse("dataset")), "7,646")
        self.assertContains(self.client.get(reverse("models")), "Train all models")

    @override_settings(TRAINING_SYNC=True)
    def test_start_training_all_models(self):
        root = Path(self._test_dataset())
        with mock.patch("registry.runner.train_candidates", return_value=[]) as train:
            resp = self.client.post(reverse("model_train"), {
                "archs": ["efficientnet", "mobilenet_v2", "resnet50"],
                "dataset_path": str(root),
                "epochs": 1,
                "fine_tune_epochs": 0,
                "model_version": "test",
                "activate_best": "on",
            })
        self.assertEqual(resp.status_code, 302)
        run = TrainingRun.objects.get()
        self.assertEqual(run.status, "done")
        self.assertEqual(run.archs, ["efficientnet", "mobilenet_v2", "resnet50"])
        train.assert_called_once()
        self.assertEqual(
            self.client.get(reverse("model_train_status", args=[run.pk])).json()["status"],
            "done",
        )

    def _test_dataset(self):
        root = Path(self._directory()) / "dataset"
        for split in ("train", "val", "test"):
            for label in ("fire", "crime", "medical_emergency", "accident", "disaster"):
                (root / split / label).mkdir(parents=True, exist_ok=True)
        return root

    def _directory(self):
        from django.conf import settings
        d = Path(settings.BASE_DIR) / ".test_train_dataset"
        d.mkdir(exist_ok=True)
        return d
