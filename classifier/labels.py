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
