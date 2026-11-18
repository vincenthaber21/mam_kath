from django.conf import settings
from django.db import models, transaction
from django.urls import reverse

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
    train_accuracy = models.FloatField(
        null=True, blank=True, help_text="Accuracy on the training images without augmentation (overfitting check)"
    )
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
        unique_together = [("name", "version")]

    def __str__(self):
        return f"{self.name} v{self.version}"

    @property
    def has_file(self):
        return bool(self.file)

    @property
    def fit(self):
        """Overfitting report (see registry/overfitting.py)."""
        from .overfitting import assess_model

        return assess_model(self)

    @classmethod
    def get_or_prepare(cls, name, version):
        """Return the existing row for name+version, or a new unsaved instance (no duplicates)."""
        existing = cls.objects.filter(name=name, version=version).order_by("-is_active", "-id").first()
        if existing:
            return existing
        return cls(name=name, version=version)

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


class SelectionSetting(models.Model):
    """Single row: how the Classify page chooses which trained model(s) to use."""

    MODES = [
        ("auto", "Automatic — highest validation accuracy"),
        ("voting", "Voting — all trained models vote"),
        ("manual", "Manual — the model you set active"),
    ]

    mode = models.CharField(max_length=10, choices=MODES, default="auto")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "model selection setting"

    def __str__(self):
        return self.get_mode_display()

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class TrainingRun(models.Model):
    """Background job that trains one or more architectures and registers them."""

    STATUS = [("pending", "Pending"), ("running", "Running"), ("done", "Done"), ("failed", "Failed")]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    archs = models.JSONField(default=list, help_text="Architecture keys being trained")
    dataset_path = models.CharField(max_length=500, default="dataset")
    epochs = models.PositiveIntegerField(default=10)
    fine_tune_epochs = models.PositiveIntegerField(default=10)
    model_version = models.CharField(max_length=20, default="1.0")
    activate_best = models.BooleanField(default=True)
    processed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    current_arch = models.CharField(max_length=40, blank=True)
    message = models.CharField(max_length=255, blank=True)
    model_ids = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"TrainingRun #{self.pk} ({self.status})"

    def get_absolute_url(self):
        return reverse("models") + f"?run={self.pk}"

    @property
    def progress_pct(self):
        return round(self.processed / self.total * 100, 1) if self.total else 0
