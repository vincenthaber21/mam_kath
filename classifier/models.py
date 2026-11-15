from django.conf import settings
from django.db import models
from django.urls import reverse

from .labels import LABEL_CHOICES, LABELS


class Classification(models.Model):
    """One submitted incident photo and its prediction (failed attempts are kept too)."""

    STATUS = [("success", "Success"), ("failed", "Failed")]
    VERIFICATION = [("correct", "Correct"), ("incorrect", "Incorrect"), ("unclear", "Unclear")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to="uploads/%Y/%m/", null=True, blank=True)
    filename = models.CharField(max_length=255, blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    size_kb = models.IntegerField(null=True, blank=True)
    model = models.ForeignKey("registry.MLModel", on_delete=models.SET_NULL, null=True, blank=True)
    demo = models.BooleanField(default=False, help_text="Simulated prediction (demo mode, no trained model)")
    predicted_label = models.CharField(max_length=30, choices=LABEL_CHOICES, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    scores = models.JSONField(default=dict, blank=True)
    low_confidence = models.BooleanField(default=False)
    inference_ms = models.FloatField(null=True, blank=True)
    reference_label = models.CharField(max_length=30, choices=LABEL_CHOICES, blank=True)
    verification = models.CharField(max_length=10, choices=VERIFICATION, blank=True)
    actual_label = models.CharField(max_length=30, choices=LABEL_CHOICES, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="success")
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["created_at"]), models.Index(fields=["predicted_label"])]

    def __str__(self):
        return f"{self.record_no} {self.predicted_label or self.status}"

    def get_absolute_url(self):
        return reverse("result", args=[self.pk])

    @property
    def record_no(self):
        return f"#{self.pk:04d}"

    @property
    def failed(self):
        return self.status == "failed"

    @property
    def has_match(self):
        return bool(self.reference_label and self.predicted_label)

    @property
    def is_match(self):
        return self.has_match and self.reference_label == self.predicted_label

    def sorted_scores(self):
        return sorted(((label, float(self.scores.get(label, 0))) for label in LABELS), key=lambda x: -x[1])
