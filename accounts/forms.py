from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from classifier.locations import barangay_choices, normalize_barangay

from .models import User, normalize_person_name, normalize_username


def _configure_barangay_field(form):
    extra = ""
    if form.is_bound:
        extra = form.data.get("barangay") or ""
    elif getattr(form, "instance", None) is not None and form.instance.pk:
        extra = form.instance.barangay or ""
    form.fields["barangay"] = forms.ChoiceField(
        choices=barangay_choices(blank_label="— Select barangay —", extra=extra),
        required=False,
        widget=forms.Select(attrs={"class": "field"}),
        help_text="Barangay in Santa Maria",
        label="Barangay / area",
    )


class EmailLoginForm(AuthenticationForm):
    """Web sign-in accepts email or username in the same field."""

    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(attrs={
            "autocomplete": "username",
            "autofocus": True,
            "class": "field",
            "placeholder": "username or you@example.com",
            "inputmode": "email",
        }),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "class": "field"}),
    )

    error_messages = {
        "invalid_login": "Username/email or password is incorrect.",
        "inactive": "This account is disabled.",
    }

    def clean_username(self):
        value = (self.cleaned_data.get("username") or "").strip()
        if "@" in value:
            return value.lower()
        return normalize_username(value) or value.lower()


# Backwards-compatible name used by older imports.
LoginForm = EmailLoginForm


def _configure_name_fields(form):
    form.fields["last_name"].required = True
    form.fields["first_name"].required = True
    form.fields["middle_name"].required = False

    form.fields["last_name"].widget.attrs.update({
        "autocomplete": "family-name",
        "placeholder": "e.g. Dela Cruz",
        "data-normalize-name": "1",
    })
    form.fields["first_name"].widget.attrs.update({
        "autocomplete": "given-name",
        "placeholder": "e.g. Juan",
        "data-normalize-name": "1",
    })
    form.fields["middle_name"].widget.attrs.update({
        "autocomplete": "additional-name",
        "placeholder": "e.g. Santos",
        "data-normalize-name": "1",
    })
    form.fields["last_name"].help_text = "Normalized to Title Case."
    form.fields["first_name"].help_text = "Normalized to Title Case."
    form.fields["middle_name"].help_text = "Optional. Normalized to Title Case."


class ManagedUserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "last_name",
            "first_name",
            "middle_name",
            "role",
            "phone",
            "barangay",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ("is_active",):
                continue
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} field".strip()
        self.fields["username"].widget.attrs.update({
            "autocomplete": "username",
            "placeholder": "e.g. juan.delacruz",
        })
        self.fields["username"].help_text = "Unique handle — letters, numbers, dots, underscores, or hyphens."
        _configure_name_fields(self)
        self.fields["email"].widget.attrs.update({"autocomplete": "email"})
        self.fields["password1"].widget.attrs.update({"class": "field", "autocomplete": "new-password"})
        self.fields["password2"].widget.attrs.update({"class": "field", "autocomplete": "new-password"})
        self.fields["role"].help_text = "Residents upload reports; officers monitor and respond."
        self.fields["is_active"].help_text = "Uncheck to disable sign-in without deleting the account."
        _configure_barangay_field(self)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_username(self):
        username = normalize_username(self.cleaned_data["username"])
        if not username:
            raise forms.ValidationError("Enter a username.")
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters.")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_last_name(self):
        value = normalize_person_name(self.cleaned_data.get("last_name") or "")
        if not value:
            raise forms.ValidationError("Enter the last name.")
        return value

    def clean_first_name(self):
        value = normalize_person_name(self.cleaned_data.get("first_name") or "")
        if not value:
            raise forms.ValidationError("Enter the first name.")
        return value

    def clean_middle_name(self):
        return normalize_person_name(self.cleaned_data.get("middle_name") or "")

    def clean_barangay(self):
        return normalize_barangay(self.cleaned_data.get("barangay"))

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.role == User.Role.ADMIN:
            user.is_staff = True
        if commit:
            user.save()
        return user


class ManagedUserEditForm(forms.ModelForm):
    password1 = forms.CharField(
        label="New password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "field", "autocomplete": "new-password"}),
        help_text="Leave blank to keep the current password.",
    )
    password2 = forms.CharField(
        label="Confirm new password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "field", "autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "last_name",
            "first_name",
            "middle_name",
            "role",
            "phone",
            "barangay",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ("is_active", "password1", "password2"):
                continue
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} field".strip()
        self.fields["username"].help_text = "Unique handle — letters, numbers, dots, underscores, or hyphens."
        _configure_name_fields(self)
        self.fields["role"].help_text = "Residents upload reports; officers monitor and respond."
        _configure_barangay_field(self)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_username(self):
        username = normalize_username(self.cleaned_data["username"])
        if not username:
            raise forms.ValidationError("Enter a username.")
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters.")
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_last_name(self):
        value = normalize_person_name(self.cleaned_data.get("last_name") or "")
        if not value:
            raise forms.ValidationError("Enter the last name.")
        return value

    def clean_first_name(self):
        value = normalize_person_name(self.cleaned_data.get("first_name") or "")
        if not value:
            raise forms.ValidationError("Enter the first name.")
        return value

    def clean_middle_name(self):
        return normalize_person_name(self.cleaned_data.get("middle_name") or "")

    def clean_barangay(self):
        return normalize_barangay(self.cleaned_data.get("barangay"))

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1") or ""
        p2 = cleaned.get("password2") or ""
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "The two password fields did not match.")
            elif len(p1) < 8:
                self.add_error("password1", "Password must be at least 8 characters.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if user.role == User.Role.ADMIN:
            user.is_staff = True
        if commit:
            user.save()
        return user
