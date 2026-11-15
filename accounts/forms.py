from django import forms
from django.contrib.auth.forms import AuthenticationForm


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True, "class": "field"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "class": "field"}),
    )

    error_messages = {
        "invalid_login": "Email or password is incorrect.",
        "inactive": "This account is disabled.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()
