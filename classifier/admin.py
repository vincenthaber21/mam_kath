from django.contrib import admin

from .models import Classification


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "predicted_label", "confidence", "reference_label", "verification", "status", "model"]
    list_filter = ["status", "predicted_label", "verification", "demo"]
    search_fields = ["filename", "id"]
    readonly_fields = ["created_at"]
