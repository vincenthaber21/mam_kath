"""The five single-label categories, in the order the model outputs them."""

LABELS = ["fire", "crime", "medical_emergency", "accident", "disaster"]
LABEL_CHOICES = [(label, label) for label in LABELS]

LABEL_NAMES = {
    "fire": "Fire",
    "crime": "Crime",
    "medical_emergency": "Medical emergency",
    "accident": "Accident",
    "disaster": "Disaster",
}

LABEL_SHORT = {
    "fire": "Fire",
    "crime": "Crime",
    "medical_emergency": "Med",
    "accident": "Acc",
    "disaster": "Dis",
}

VERIFICATION_CHOICES = [
    ("correct", "Correct"),
    ("incorrect", "Incorrect — actual is…"),
    ("unclear", "Unclear or multiple events"),
]


def label_name(label):
    if not label:
        return "—"
    return LABEL_NAMES.get(label, label)


def display_prediction(rec):
    """Human-facing prediction: Uncertain when no category was assigned."""
    if getattr(rec, "low_confidence", False) or not getattr(rec, "predicted_label", None):
        if getattr(rec, "status", "success") == "failed":
            return "—"
        if not rec.predicted_label:
            return "Uncertain"
    return label_name(rec.predicted_label)
