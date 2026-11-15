from django.db import models, transaction

from classifier.labels import LABEL_CHOICES


class MLModel(models.Model):
    """A trained transfer-learning candidate (EfficientNet, MobileNetV2, ResNet50...)."""

    PREPROC = [
        ("efficientnet", "EfficientNet"),
        ("mobilenet_v2", "MobileNetV2"),
        ("resnet50", "ResNet50"),
    ]

    name = models.CharField(max_length=80)
    version = models.CharField(max_length=20, default="1.0")
    file = models.FileField(upload_to="models/", blank=True, help_text=".h5 or .keras file")
    labels_json = models.JSONField(default=list, help_text="Class labels in the order the model outputs them")
    input_size = models.PositiveIntegerField(default=224)
    preprocessing = models.CharField(max_length=20, choices=PREPROC, default="efficientnet")
    val_accuracy = models.FloatField(null=True, blank=True)
    val_macro_f1 = models.FloatField(null=True, blank=True)
    test_accuracy = models.FloatField(null=True, blank=True)
    size_mb = models.FloatField(null=True, blank=True)
    avg_inference_ms = models.FloatField(null=True, blank=True)
    history = models.JSONField(
        default=list,
        blank=True,
        help_text='Per-epoch list: [{"epoch":1,"train_acc":..,"val_acc":..,"train_loss":..,"val_loss":..}]',
    )
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "ML model"

    def __str__(self):
        return f"{self.name} v{self.version}"

    @property
    def has_file(self):
        return bool(self.file)

    def save(self, *args, **kwargs):
        # Only one model may be active at a time.
        with transaction.atomic():
            if self.is_active:
                MLModel.objects.exclude(pk=self.pk).filter(is_active=True).update(is_active=False)
            super().save(*args, **kwargs)


class DatasetSplit(models.Model):
    """Image counts per class and split, filled by `manage.py import_dataset_counts`."""

    SPLITS = [("train", "Train"), ("val", "Validation"), ("test", "Test")]

    label = models.CharField(max_length=30, choices=LABEL_CHOICES)
    split = models.CharField(max_length=5, choices=SPLITS)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("label", "split")]
        ordering = ["label", "split"]

    def __str__(self):
        return f"{self.label}/{self.split}: {self.count}"


class DatasetInfo(models.Model):
    """Single row describing where the dataset came from and how many images were removed."""

    sources = models.CharField(max_length=300, blank=True, default="Kaggle Emergency Scene Dataset, Google Open Images")
    removed = models.PositiveIntegerField(default=0, help_text="Duplicate or corrupt images removed during cleaning")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "dataset info"
        verbose_name_plural = "dataset info"

    def __str__(self):
        return "Dataset info"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
