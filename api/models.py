import secrets

from django.conf import settings
from django.db import models


def generate_key():
    return secrets.token_hex(32)


class AuthToken(models.Model):
    """Bearer token for the mobile / JSON API (not used by the website forms)."""

    key = models.CharField(max_length=64, unique=True, default=generate_key, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    label = models.CharField(max_length=80, blank=True, help_text="e.g. phone model")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} · {self.key[:8]}…"
