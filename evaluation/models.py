from django.conf import settings
from django.db import models
from django.urls import reverse

from classifier.labels import LABEL_CHOICES


class Evaluation(models.Model):
    STATUS = [("running", "Running"), ("done", "Done"), ("failed", "Failed")]

    model = models.ForeignKey("registry.MLModel", on_delete=models.SET_NULL, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    test_set = models.FileField(upload_to="test_sets/")
    test_set_name = models.CharField(max_length=255, blank=True)
    update_model_metrics = models.BooleanField(default=True)
    demo = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS, default="running")
    processed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    accuracy = models.FloatField(null=True, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    inference_ms = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Evaluation #{self.pk} ({self.status})"

    def get_absolute_url(self):
        return reverse("evaluation") + f"?id={self.pk}"

    @property
    def progress_pct(self):
        return round(self.processed / self.total * 100, 1) if self.total else 0


class Misclassified(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="misclassified")
    image = models.ImageField(upload_to="evaluations/")
    filename = models.CharField(max_length=255, blank=True)
    actual = models.CharField(max_length=30, choices=LABEL_CHOICES)
    predicted = models.CharField(max_length=30, choices=LABEL_CHOICES)
    confidence = models.FloatField()

    class Meta:
        ordering = ["-confidence"]
        verbose_name_plural = "misclassified images"
