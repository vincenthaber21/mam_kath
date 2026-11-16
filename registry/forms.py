import json
from pathlib import Path

from django import forms
from django.conf import settings

from classifier.labels import LABELS

from .models import MLModel
from .training import ALL_ARCHS, ARCHS

MAX_MODEL_MB = 500

ARCH_CHOICES = [(k, ARCHS[k][0]) for k in ALL_ARCHS]


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


class TrainModelsForm(forms.Form):
    archs = forms.MultipleChoiceField(
        label="Architectures",
        choices=ARCH_CHOICES,
        initial=list(ALL_ARCHS),
        widget=forms.CheckboxSelectMultiple,
        help_text="Train every selected model in one run, then activate the best by validation macro F1.",
    )
    dataset_path = forms.CharField(
        label="Dataset folder",
        initial="dataset",
        widget=forms.TextInput(attrs={"class": "field"}),
        help_text="Folder with train/, val/ and test/ sub-folders (relative to the project root, or absolute).",
    )
    epochs = forms.IntegerField(
        label="Head-training epochs",
        initial=10,
        min_value=1,
        max_value=100,
        widget=forms.NumberInput(attrs={"class": "field"}),
    )
    fine_tune_epochs = forms.IntegerField(
        label="Fine-tune epochs",
        initial=10,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={"class": "field"}),
    )
    model_version = forms.CharField(
        label="Version tag",
        initial="1.0",
        max_length=20,
        widget=forms.TextInput(attrs={"class": "field"}),
    )
    activate_best = forms.BooleanField(
        label="Activate the best model when finished",
        required=False,
        initial=True,
    )

    def clean_dataset_path(self):
        raw = self.cleaned_data["dataset_path"].strip()
        path = Path(raw)
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        for split in ("train", "val"):
            if not (path / split).is_dir():
                raise forms.ValidationError(f"Missing folder: {path / split}")
        return str(path)
