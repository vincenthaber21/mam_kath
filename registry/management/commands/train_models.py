"""Train and compare transfer-learning candidates (Objective 1) and register them on the Models page.

Dataset layout (same as import_dataset_counts):
    <path>/train/<label>/*.jpg   <path>/val/<label>/*.jpg   <path>/test/<label>/*.jpg
with label folders fire, crime, medical_emergency, accident, disaster.

Each candidate is an ImageNet-pretrained backbone with a new softmax head:
  phase 1  backbone frozen, train the head
  phase 2  unfreeze the top `--fine-tune-layers` layers and fine-tune with a low learning rate
Validation accuracy / macro F1, test accuracy, file size, average single-image inference time and the
per-epoch history are saved with the model. The candidate with the best validation macro F1 is activated.

Train every architecture at once:
    python manage.py train_models dataset --all
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from registry.training import ALL_ARCHS, ARCHS, train_candidates


class Command(BaseCommand):
    help = "Train EfficientNet-B0 / MobileNetV2 / ResNet50 by transfer learning and register them on the Models page."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Dataset folder with train/, val/ and test/ sub-folders")
        parser.add_argument(
            "--archs",
            default="",
            help="Comma-separated: efficientnet, mobilenet_v2, resnet50 (default: all three)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Train EfficientNet-B0, MobileNetV2 and ResNet50 in one run (same as omitting --archs)",
        )
        parser.add_argument("--epochs", type=int, default=10, help="Epochs with the backbone frozen")
        parser.add_argument("--fine-tune-epochs", type=int, default=10, help="Epochs fine-tuning the top layers")
        parser.add_argument("--fine-tune-layers", type=int, default=20)
        parser.add_argument("--batch-size", type=int, default=32)
        parser.add_argument("--input-size", type=int, default=224)
        parser.add_argument("--model-version", default="1.0")
        parser.add_argument("--out", default="trained_models", help="Where .keras files are written")
        parser.add_argument("--no-activate", action="store_true", help="Do not activate the best model")
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="One line per epoch instead of a live progress bar (good for log files)",
        )
        parser.add_argument(
            "--run-id",
            type=int,
            default=None,
            help="Optional TrainingRun id to update while training (used by the Models page)",
        )

    def handle(self, *args, **o):
        if o["all"] or not o["archs"].strip():
            archs = list(ALL_ARCHS)
        else:
            archs = [a.strip() for a in o["archs"].split(",") if a.strip()]
        bad = [a for a in archs if a not in ARCHS]
        if bad:
            raise CommandError(f"Unknown architecture(s): {', '.join(bad)}")

        run = None
        if o["run_id"] is not None:
            from registry.models import TrainingRun

            try:
                run = TrainingRun.objects.get(pk=o["run_id"])
            except TrainingRun.DoesNotExist as exc:
                raise CommandError(f"TrainingRun {o['run_id']} not found") from exc
            TrainingRun.objects.filter(pk=run.pk).update(
                status="running",
                total=len(archs),
                processed=0,
                message=f"Starting {len(archs)} model(s)",
                error="",
            )

        def on_progress(**kwargs):
            if run is None:
                return
            from registry.models import TrainingRun

            fields = {
                "processed": kwargs.get("processed", 0),
                "total": kwargs.get("total", len(archs)),
                "current_arch": kwargs.get("current_arch", ""),
                "message": kwargs.get("message", ""),
            }
            if "model_ids" in kwargs:
                fields["model_ids"] = kwargs["model_ids"]
            TrainingRun.objects.filter(pk=run.pk).update(**fields)

        def write(msg=""):
            self.stdout.write(str(msg))

        try:
            trained = train_candidates(
                o["path"],
                archs,
                epochs=o["epochs"],
                fine_tune_epochs=o["fine_tune_epochs"],
                fine_tune_layers=o["fine_tune_layers"],
                batch_size=o["batch_size"],
                input_size=o["input_size"],
                model_version=o["model_version"],
                out=o["out"],
                activate=not o["no_activate"],
                quiet=o["quiet"],
                write=write,
                on_progress=on_progress,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            if run is not None:
                from registry.models import TrainingRun

                TrainingRun.objects.filter(pk=run.pk).update(
                    status="failed", error=str(exc), finished_at=timezone.now(),
                )
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            if run is not None:
                from registry.models import TrainingRun

                TrainingRun.objects.filter(pk=run.pk).update(
                    status="failed", error=str(exc), finished_at=timezone.now(),
                )
            raise

        if run is not None:
            from registry.models import TrainingRun

            TrainingRun.objects.filter(pk=run.pk).update(
                status="done",
                processed=len(archs),
                total=len(archs),
                message=f"Done — {len(trained)} model(s) registered",
                model_ids=[m.id for m in trained],
                finished_at=timezone.now(),
            )

        for m in trained:
            self.stdout.write(self.style.SUCCESS(
                f"{m.name}: val acc {m.val_accuracy}, val macro F1 {m.val_macro_f1}, "
                f"test acc {m.test_accuracy}, {m.size_mb} MB, {m.avg_inference_ms} ms, "
                f"fit: {m.fit.label} -> registered (id {m.id})"
            ))
        if trained and not o["no_activate"]:
            from registry.training import pick_best

            best = pick_best(trained)
            self.stdout.write(self.style.SUCCESS(
                f"\nActive model: {best} (best validation macro F1 among models that do not overfit)."
            ))
