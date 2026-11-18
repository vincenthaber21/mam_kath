import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from classifier.labels import LABELS
from registry.models import MLModel


class Command(BaseCommand):
    help = "Register a trained Keras model file (.h5/.keras) so the website can use it."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the .h5 or .keras file")
        parser.add_argument("--name", required=True, help='e.g. "EfficientNet-B0"')
        parser.add_argument("--version", default="1.0")
        parser.add_argument("--preprocessing", choices=[c for c, _ in MLModel.PREPROC], required=True)
        parser.add_argument("--input-size", type=int, default=224)
        parser.add_argument("--labels", default=json.dumps(LABELS), help="JSON list in the model's output order")
        parser.add_argument("--train-accuracy", type=float, help="Accuracy on un-augmented training images")
        parser.add_argument("--val-accuracy", type=float)
        parser.add_argument("--val-macro-f1", type=float)
        parser.add_argument("--test-accuracy", type=float)
        parser.add_argument("--history", help="Path to a JSON file with per-epoch history")
        parser.add_argument("--notes", default="")
        parser.add_argument("--activate", action="store_true", help="Make this the active model")

    def handle(self, *args, **opts):
        path = Path(opts["path"])
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        if path.suffix.lower() not in {".h5", ".keras"}:
            raise CommandError("The model must be a .h5 or .keras file.")
        try:
            labels = json.loads(opts["labels"])
        except json.JSONDecodeError as exc:
            raise CommandError(f"--labels is not valid JSON: {exc}")
        if sorted(labels) != sorted(LABELS):
            raise CommandError("--labels must contain exactly: " + ", ".join(LABELS))
        history = []
        if opts["history"]:
            history = json.loads(Path(opts["history"]).read_text())

        m = MLModel.get_or_prepare(opts["name"], opts["version"])
        replacing = bool(m.pk)
        m.preprocessing = opts["preprocessing"]
        m.input_size = opts["input_size"]
        m.labels_json = labels
        m.train_accuracy = opts["train_accuracy"]
        m.val_accuracy = opts["val_accuracy"]
        m.val_macro_f1 = opts["val_macro_f1"]
        m.test_accuracy = opts["test_accuracy"]
        m.size_mb = round(path.stat().st_size / 1024 / 1024, 1)
        m.history = history
        m.notes = opts["notes"]
        if opts["activate"]:
            m.is_active = True
        if m.file:
            m.file.delete(save=False)
        with path.open("rb") as fh:
            m.file.save(path.name, File(fh), save=False)
        m.save()
        verb = "Updated" if replacing else "Registered"
        state = " and activated it" if m.is_active else ""
        self.stdout.write(self.style.SUCCESS(f"{verb} {m}{state} (id {m.id}). Fit check: {m.fit.label}. {m.fit.summary}"))
