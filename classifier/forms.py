from django import forms

from .labels import LABEL_NAMES, LABELS, VERIFICATION_CHOICES
from .locations import barangay_choices, normalize_barangay
from .models import IncidentResponse, NotifyAgency


class VerificationForm(forms.Form):
    verification = forms.ChoiceField(choices=VERIFICATION_CHOICES)
    actual_label = forms.ChoiceField(
        choices=[("", "Select the actual category")] + [(l, LABEL_NAMES[l]) for l in LABELS],
        required=False,
    )

    def __init__(self, *args, record=None, **kwargs):
        self.record = record
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        choice = data.get("verification")
        actual = data.get("actual_label")
        if choice == "incorrect":
            if not actual:
                self.add_error("actual_label", "Select the actual category.")
            elif self.record and actual == self.record.predicted_label:
                self.add_error("actual_label", "The actual category must differ from the prediction.")
        elif choice == "correct":
            if self.record and not self.record.predicted_label:
                self.add_error(
                    "verification",
                    "No category was assigned — choose Unclear, or Incorrect with the actual category.",
                )
            else:
                data["actual_label"] = self.record.predicted_label if self.record else ""
        else:
            data["actual_label"] = ""
        return data


class IncidentResponseForm(forms.Form):
    action = forms.ChoiceField(choices=IncidentResponse.Action.choices)
    message = forms.CharField(
        widget=forms.Textarea(attrs={"class": "field", "rows": 4, "placeholder": "What happened, what you are doing, or an update for responders…"}),
        max_length=4000,
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["action"].widget.attrs["class"] = "field"
        # Residents may only leave comments; officers can change operational status.
        if user is not None and not getattr(user, "can_monitor_incidents", False):
            self.fields["action"].choices = [
                (IncidentResponse.Action.COMMENT, "Comment"),
            ]

    def clean(self):
        data = super().clean()
        action = data.get("action")
        message = (data.get("message") or "").strip()
        if action == IncidentResponse.Action.COMMENT and not message:
            self.add_error("message", "Enter a follow-up message.")
        data["message"] = message
        return data


class NotifyAgencyForm(forms.ModelForm):
    class Meta:
        model = NotifyAgency
        fields = (
            "name",
            "agency_type",
            "contact_name",
            "phone",
            "email",
            "barangay",
            "address",
            "latitude",
            "longitude",
            "notes",
            "is_active",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "latitude": forms.NumberInput(attrs={"step": "any", "inputmode": "decimal", "data-agency-lat": ""}),
            "longitude": forms.NumberInput(attrs={"step": "any", "inputmode": "decimal", "data-agency-lng": ""}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "is_active":
                continue
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} field".strip()
        self.fields["name"].widget.attrs["placeholder"] = "e.g. Barangay Fire Station"
        self.fields["contact_name"].widget.attrs["placeholder"] = "e.g. Duty officer"
        self.fields["phone"].widget.attrs.update({"placeholder": "e.g. 09171234567", "inputmode": "tel"})
        self.fields["email"].widget.attrs.update({"placeholder": "agency@example.com", "autocomplete": "email"})
        extra = ""
        if self.is_bound:
            extra = self.data.get("barangay") or ""
        elif self.instance and self.instance.pk:
            extra = self.instance.barangay or ""
        self.fields["barangay"] = forms.ChoiceField(
            choices=barangay_choices(blank_label="— Select barangay —", extra=extra),
            required=False,
            widget=forms.Select(attrs={"class": "field"}),
            help_text="Coverage barangay in Santa Maria",
        )
        self.fields["address"].widget.attrs["placeholder"] = "Street / landmark"
        self.fields["latitude"].widget.attrs["placeholder"] = "e.g. 17.35712"
        self.fields["longitude"].widget.attrs["placeholder"] = "e.g. 120.49634"
        self.fields["notes"].widget.attrs["placeholder"] = "Hours, radio channel, or how to notify…"
        self.fields["agency_type"].help_text = "Used to suggest this agency for matching incident categories."
        self.fields["is_active"].help_text = "Uncheck to hide from notify pickers without deleting."

    def clean_barangay(self):
        return normalize_barangay(self.cleaned_data.get("barangay"))

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("Enter the agency name.")
        return name

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        return email

    def clean(self):
        cleaned = super().clean()
        phone = (cleaned.get("phone") or "").strip()
        email = cleaned.get("email") or ""
        if not phone and not email:
            raise forms.ValidationError("Provide at least a phone number or email so the agency can be notified.")
        cleaned["phone"] = phone
        lat = cleaned.get("latitude")
        lng = cleaned.get("longitude")
        if (lat is None) != (lng is None):
            self.add_error("latitude" if lat is None else "longitude", "Enter both latitude and longitude, or leave both blank.")
        else:
            if lat is not None and not -90 <= lat <= 90:
                self.add_error("latitude", "Latitude must be between -90 and 90.")
            if lng is not None and not -180 <= lng <= 180:
                self.add_error("longitude", "Longitude must be between -180 and 180.")
        return cleaned
