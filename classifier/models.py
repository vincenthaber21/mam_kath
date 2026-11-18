from django.conf import settings
from django.db import models
from django.urls import reverse

from .labels import LABEL_CHOICES, LABELS


class Classification(models.Model):
    """One submitted incident photo and its prediction (failed attempts are kept too)."""

    STATUS = [("success", "Success"), ("failed", "Failed")]
    VERIFICATION = [("correct", "Correct"), ("incorrect", "Incorrect"), ("unclear", "Unclear")]
    RESPONSE_STATUS = [
        ("open", "Pending"),
        ("acknowledged", "Acknowledged"),
        ("responding", "Responding"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to="uploads/%Y/%m/", null=True, blank=True)
    filename = models.CharField(max_length=255, blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    size_kb = models.IntegerField(null=True, blank=True)
    model = models.ForeignKey("registry.MLModel", on_delete=models.SET_NULL, null=True, blank=True,
                              help_text="The model whose prediction was used (the deciding model when voting)")
    selection_mode = models.CharField(max_length=10, blank=True, help_text="auto, voting or manual")
    votes = models.JSONField(default=list, blank=True,
                             help_text="Voting mode: one entry per model with its label and confidence")
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
    # Optional incident-report context from the mobile app (or web form).
    notes = models.TextField(blank=True, help_text="Reporter notes / what happened")
    location_text = models.CharField(max_length=255, blank=True, help_text="Place description")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    source = models.CharField(
        max_length=10,
        blank=True,
        default="web",
        help_text="web or mobile — where the report was submitted",
    )
    response_status = models.CharField(
        max_length=20,
        choices=RESPONSE_STATUS,
        default="open",
        help_text="Operational status for officers monitoring the incident",
    )
    assigned_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_incidents",
        help_text="Officer currently handling this incident",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["predicted_label"]),
            models.Index(fields=["response_status"]),
        ]

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

    @property
    def response_status_label(self):
        return dict(self.RESPONSE_STATUS).get(self.response_status, self.response_status)


class IncidentResponse(models.Model):
    """A resident follow-up or officer action on a reported incident."""

    class Action(models.TextChoices):
        COMMENT = "comment", "Comment"
        ACKNOWLEDGE = "acknowledge", "Acknowledge"
        RESPONDING = "responding", "Responding"
        CANCEL = "cancel", "Cancel"
        RESOLVE = "resolve", "Mark resolved"
        CLOSE = "close", "Close"
        REOPEN = "reopen", "Reopen"

    ACTION_TO_STATUS = {
        Action.ACKNOWLEDGE: "acknowledged",
        Action.RESPONDING: "responding",
        Action.CANCEL: "open",
        Action.RESOLVE: "resolved",
        Action.CLOSE: "closed",
        Action.REOPEN: "open",
    }

    DEFAULT_MESSAGES = {
        Action.ACKNOWLEDGE: "Incident acknowledged.",
        Action.RESPONDING: "Officer is responding to this incident.",
        Action.CANCEL: "Response cancelled. Report is pending again.",
        Action.RESOLVE: "Incident marked resolved.",
        Action.CLOSE: "Incident closed.",
        Action.REOPEN: "Incident reopened and pending again.",
    }

    incident = models.ForeignKey(
        Classification,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incident_responses",
    )
    action = models.CharField(max_length=20, choices=Action.choices, default=Action.COMMENT)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.get_action_display()} on {self.incident.record_no}"

    @property
    def action_label(self):
        return self.get_action_display()


class NotifyAgency(models.Model):
    """Contact directory for agencies officers may notify about an incident."""

    class AgencyType(models.TextChoices):
        FIRE = "fire", "Fire"
        CRIME = "crime", "Crime / police"
        MEDICAL = "medical_emergency", "Medical emergency"
        ACCIDENT = "accident", "Accident"
        DISASTER = "disaster", "Disaster"
        GENERAL = "general", "General / other"

    name = models.CharField(max_length=200)
    agency_type = models.CharField(
        max_length=30,
        choices=AgencyType.choices,
        default=AgencyType.GENERAL,
        help_text="Incident category this agency typically handles",
    )
    contact_name = models.CharField(max_length=200, blank=True, help_text="Desk officer or unit contact")
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    barangay = models.CharField(max_length=120, blank=True, help_text="Barangay or coverage area")
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True, help_text="Agency station location (Santa Maria map pin)")
    longitude = models.FloatField(null=True, blank=True, help_text="Agency station location (Santa Maria map pin)")
    notes = models.TextField(blank=True, help_text="Hours, radio channel, or other notify instructions")
    is_active = models.BooleanField(default=True, help_text="Inactive agencies stay listed but are hidden from notify pickers")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        verbose_name_plural = "notify agencies"
        indexes = [
            models.Index(fields=["agency_type"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    @property
    def agency_type_label(self):
        return self.get_agency_type_display()

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None
