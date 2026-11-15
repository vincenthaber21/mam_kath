import math

from django.core.management.base import BaseCommand

from classifier.labels import LABELS
from registry.models import DatasetInfo, DatasetSplit, MLModel


def make_history(seed, final_acc, epochs=20):
    rows = []
    for e in range(1, epochs + 1):
        t = e / epochs
        wobble = math.sin(e * 1.7 + seed) * 0.008
        train_acc = min(0.99, 0.45 + (final_acc + 0.06 - 0.45) * (1 - math.exp(-4 * t)) + wobble)
        val_acc = 0.42 + (final_acc - 0.42) * (1 - math.exp(-3.5 * t)) + wobble * 1.5
        rows.append({
            "epoch": e,
            "train_acc": round(train_acc, 4),
            "val_acc": round(val_acc, 4),
            "train_loss": round(1.6 * math.exp(-3 * t) + 0.12 - wobble, 4),
            "val_loss": round(1.6 * math.exp(-2.6 * t) + 0.28 + abs(wobble) * 2, 4),
        })
    return rows


class Command(BaseCommand):
    help = "Fill the Models and Dataset pages with example numbers so you can try the website."

    def handle(self, *args, **opts):
        demo = [
            ("EfficientNet-B0", "efficientnet", 0.894, 0.889, 0.885, 16.3, 142, "ImageNet weights, fine-tuned top 20 layers.", True),
            ("MobileNetV2", "mobilenet_v2", 0.861, 0.855, 0.852, 9.4, 88, "Lightweight candidate for phones.", False),
            ("ResNet50", "resnet50", 0.872, 0.868, 0.866, 94.7, 231, "Largest candidate.", False),
        ]
        for i, (name, pre, va, vf, ta, size, inf, notes, active) in enumerate(demo):
            if MLModel.objects.filter(name=name, version="1.0").exists():
                continue
            MLModel.objects.create(
                name=name, version="1.0", preprocessing=pre, labels_json=LABELS, val_accuracy=va,
                val_macro_f1=vf, test_accuracy=ta, size_mb=size, avg_inference_ms=inf,
                history=make_history(i * 11, va), notes=f"[Example] {notes}", is_active=active,
            )
        counts = {"fire": 1180, "crime": 940, "medical_emergency": 1012, "accident": 1096, "disaster": 1124}
        for label, train in counts.items():
            other = round(train * 0.2143)
            for split, n in (("train", train), ("val", other), ("test", other)):
                DatasetSplit.objects.update_or_create(label=label, split=split, defaults={"count": n})
        info = DatasetInfo.get()
        info.removed = 187
        info.save()
        self.stdout.write(self.style.SUCCESS(
            "Example models and dataset counts added. Replace them with your real ones before your defence."
        ))
