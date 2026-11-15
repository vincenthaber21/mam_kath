import zipfile

from django import forms
from django.conf import settings

from registry.models import MLModel


class EvaluationForm(forms.Form):
    test_set = forms.FileField(widget=forms.ClearableFileInput(attrs={"accept": ".zip,application/zip"}))
    model = forms.ModelChoiceField(queryset=MLModel.objects.all(), empty_label=None)
    update_model_metrics = forms.BooleanField(
        required=False, initial=True, label="Save the test accuracy and mean inference time to the model comparison"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["model"].label_from_instance = lambda m: f"{m.name} v{m.version}" + (" (active)" if m.is_active else "")
        active = MLModel.objects.filter(is_active=True).first()
        if active:
            self.fields["model"].initial = active.pk

    def clean_test_set(self):
        f = self.cleaned_data["test_set"]
        if not f.name.lower().endswith(".zip"):
            raise forms.ValidationError("Upload a .zip file with one folder per category.")
        if f.size > settings.MAX_TEST_SET_MB * 1024 * 1024:
            raise forms.ValidationError(f"The test set can be at most {settings.MAX_TEST_SET_MB} MB.")
        if not zipfile.is_zipfile(f):
            raise forms.ValidationError("This file is not a valid .zip archive.")
        f.seek(0)
        return f
