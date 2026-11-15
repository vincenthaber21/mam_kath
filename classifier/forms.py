from django import forms

from .labels import LABEL_NAMES, LABELS, VERIFICATION_CHOICES


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
            data["actual_label"] = self.record.predicted_label if self.record else ""
        else:
            data["actual_label"] = ""
        return data
