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

    def test_get_or_prepare_reuses_same_name_version(self):
        first = MLModel.objects.create(name="EfficientNet-B0", version="1.0", val_accuracy=0.9)
        second = MLModel.get_or_prepare("EfficientNet-B0", "1.0")
        self.assertEqual(second.pk, first.pk)
        fresh = MLModel.get_or_prepare("MobileNetV2", "1.0")
        self.assertIsNone(fresh.pk)

    def test_seed_demo_and_pages_render(self):
        call_command("seed_demo", verbosity=0)
        self.assertEqual(MLModel.objects.count(), 3)
        for name in ("dashboard", "classify", "history", "evaluation", "models", "dataset"):
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


class OverfittingCheckTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("o@example.com", "pass-1234-word"))

    def test_good_fit(self):
        from .overfitting import assess

        r = assess(train_accuracy=0.995, val_accuracy=0.989, test_accuracy=0.991)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.reasons, [])

    def test_train_val_gap_flags_overfit(self):
        from .overfitting import assess

        self.assertEqual(assess(train_accuracy=1.0, val_accuracy=0.96).status, "watch")
        r = assess(train_accuracy=1.0, val_accuracy=0.90, test_accuracy=0.89)
        self.assertEqual(r.status, "overfit")
        self.assertIn("above validation", r.summary)

    def test_val_test_gap_flags_overfit(self):
        from .overfitting import assess

        self.assertEqual(assess(val_accuracy=0.98, test_accuracy=0.90).status, "overfit")

    def test_history_fallback_and_loss_divergence(self):
        from .overfitting import assess

        history = [
            {"epoch": 1, "train_acc": 0.80, "val_acc": 0.79, "train_loss": 0.60, "val_loss": 0.62},
            {"epoch": 2, "train_acc": 0.90, "val_acc": 0.89, "train_loss": 0.30, "val_loss": 0.35},
            {"epoch": 3, "train_acc": 0.95, "val_acc": 0.88, "train_loss": 0.15, "val_loss": 0.45},
        ]
        r = assess(val_accuracy=0.89, history=history)
        self.assertEqual(r.train_val_gap, 0.01)  # measured at the best epoch (2), not the last
        self.assertIn("epoch 2", r.train_val_source)
        self.assertEqual(r.status, "watch")
        self.assertIn("Validation loss rose", r.summary)

    def test_unknown_without_numbers(self):
        from .overfitting import assess

        self.assertEqual(assess().status, "unknown")

    def test_auto_selection_skips_overfit_model(self):
        from django.core.files.base import ContentFile

        from classifier.services import best_model
        from .training import pick_best

        over = MLModel(name="Over", train_accuracy=1.0, val_accuracy=0.99, val_macro_f1=0.99, test_accuracy=0.90)
        good = MLModel(name="Good", train_accuracy=0.97, val_accuracy=0.96, val_macro_f1=0.96, test_accuracy=0.96)
        for m in (over, good):
            m.file.save(f"{m.name}.keras", ContentFile(b"x"), save=False)
            m.save()
        self.assertEqual(best_model().pk, good.pk)
        self.assertEqual(pick_best([over, good]).pk, good.pk)
        self.assertEqual(pick_best([over]).pk, over.pk)  # still picks something if all overfit
        for m in (over, good):
            m.file.delete(save=False)

    def test_models_page_shows_fit_column(self):
        MLModel.objects.create(name="Over", train_accuracy=1.0, val_accuracy=0.90, test_accuracy=0.89)
        resp = self.client.get(reverse("models"))
        self.assertContains(resp, "Overfitting check")
        self.assertContains(resp, "badge-fit-overfit")
        self.assertContains(resp, "+10.0 pts")


class RegularizationLayerTests(TestCase):
    def test_classifier_head_has_anti_overfitting_layers(self):
        import unittest

        try:
            import tensorflow as tf
        except ImportError:
            raise unittest.SkipTest("TensorFlow not installed")
        import numpy as np

        from .training import DROPOUT_RATE, build_augmentation, build_classifier

        base = tf.keras.applications.MobileNetV2(include_top=False, weights=None, input_shape=(64, 64, 3))
        model = build_classifier(tf, base, 64, 5)
        names = [layer.name for layer in model.layers]
        self.assertIn("head_bn", names)
        self.assertEqual(model.get_layer("head_dropout").rate, DROPOUT_RATE)
        self.assertIsNotNone(model.get_layer("predictions").kernel_regularizer)

        x = np.random.randint(0, 255, (2, 64, 64, 3)).astype("float32")
        aug = build_augmentation(tf)
        self.assertTrue(np.allclose(aug(x, training=False).numpy(), x))  # never changes predictions
