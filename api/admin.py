from django.contrib import admin

from .models import AuthToken


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("key_prefix", "user", "label", "created_at", "last_used_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "label", "key")
    readonly_fields = ("key", "created_at", "last_used_at")

    @admin.display(description="Token")
    def key_prefix(self, obj):
        return f"{obj.key[:8]}…"
