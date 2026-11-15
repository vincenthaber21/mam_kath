from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from classifier.labels import LABELS
from registry.models import DatasetInfo, DatasetSplit

IMAGE_EXT = {".jpg", ".jpeg", ".png"}
SPLIT_ALIASES = {"train": "train", "val": "val", "valid": "val", "validation": "val", "test": "test"}


class Command(BaseCommand):
    help = (
        "Count images in a dataset folder laid out as <path>/<train|val|test>/<label>/*.jpg "
        "and save the counts for the Dataset page."
    )

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--removed", type=int, help="Number of duplicate/corrupt images removed while cleaning")
        parser.add_argument("--sources", help='e.g. "Kaggle Emergency Scene Dataset, Google Open Images"')

    def handle(self, *args, **opts):
        root = Path(opts["path"])
        if not root.is_dir():
            raise CommandError(f"Folder not found: {root}")
        found = 0
        for split_dir in root.iterdir():
            split = SPLIT_ALIASES.get(split_dir.name.lower())
            if not split or not split_dir.is_dir():
                continue
            for label in LABELS:
                label_dir = split_dir / label
                n = 0
                if label_dir.is_dir():
                    n = sum(1 for p in label_dir.rglob("*") if p.suffix.lower() in IMAGE_EXT)
                DatasetSplit.objects.update_or_create(label=label, split=split, defaults={"count": n})
                found += n
                self.stdout.write(f"{split:5} {label:18} {n}")
        if not found:
            raise CommandError("No images found. Expected sub-folders train/, val/ and test/ with one folder per label.")
        info = DatasetInfo.get()
        if opts["removed"] is not None:
            info.removed = opts["removed"]
        if opts["sources"]:
            info.sources = opts["sources"]
        info.save()
        self.stdout.write(self.style.SUCCESS(f"Saved counts for {found} images."))
