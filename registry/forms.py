import json

from django import forms

from classifier.labels import LABELS

from .models import MLModel

MAX_MODEL_MB = 500


class ModelUploadForm(forms.ModelForm):
    labels_text = forms.CharField(
        label="Class labels (JSON list, in output order)",
        initial=json.dumps(LABELS),
        widget=forms.TextInput(attrs={"class": "field"}),
    )

    class Meta:
        model = MLModel
        fields = ["name", "version", "preprocessing", "input_size", "file", "val_accuracy", "val_macro_f1", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "field", "placeholder": "EfficientNet-B0"}),
            "version": forms.TextInput(attrs={"class": "field"}),
            "preprocessing": forms.Select(attrs={"class": "field"}),
            "input_size": forms.NumberInput(attrs={"class": "field"}),
            "file": forms.ClearableFileInput(attrs={"class": "field-file", "accept": ".h5,.keras"}),
            "val_accuracy": forms.NumberInput(attrs={"class": "field", "step": "0.001", "min": 0, "max": 1}),
            "val_macro_f1": forms.NumberInput(attrs={"class": "field", "step": "0.001", "min": 0, "max": 1}),
            "notes": forms.Textarea(attrs={"class": "field", "rows": 3}),
        }
        labels = {
            "val_accuracy": "Validation accuracy (0-1, optional)",
            "val_macro_f1": "Validation macro F1 (0-1, optional)",
            "input_size": "Input size (px)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].required = True

    def clean_file(self):
        f = self.cleaned_data["file"]
        name = f.name.lower()
        if not (name.endswith(".h5") or name.endswith(".keras")):
            raise forms.ValidationError("Upload a .h5 or .keras model file.")
        if f.size > MAX_MODEL_MB * 1024 * 1024:
            raise forms.ValidationError(f"Model files can be at most {MAX_MODEL_MB} MB.")
        return f

    def clean_labels_text(self):
        raw = self.cleaned_data["labels_text"]
        try:
            labels = json.loads(raw)
        except json.JSONDecodeError:
            raise forms.ValidationError('Enter a JSON list, for example ["fire","crime",...].')
        if not isinstance(labels, list) or sorted(labels) != sorted(LABELS):
            raise forms.ValidationError("The list must contain exactly these five labels: " + ", ".join(LABELS) + ".")
        return labels

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.labels_json = self.cleaned_data["labels_text"]
        obj.size_mb = round(self.cleaned_data["file"].size / 1024 / 1024, 1)
        if commit:
            obj.save()
        return obj
