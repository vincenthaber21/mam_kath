from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["last_name", "first_name", "email"]
    list_display = ["username", "last_name", "first_name", "middle_name", "email", "role", "barangay", "is_active"]
    list_filter = ["role", "is_staff", "is_active"]
    search_fields = ["username", "email", "first_name", "middle_name", "last_name", "name", "phone", "barangay"]
    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        ("Profile", {"fields": ("last_name", "first_name", "middle_name", "name", "role", "phone", "barangay")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ["name"]
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "email",
                "last_name", "first_name", "middle_name",
                "role", "phone", "barangay",
                "password1", "password2",
            ),
        }),
    )
