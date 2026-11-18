from django.contrib import admin

from .models import Classification, IncidentResponse, NotifyAgency


class IncidentResponseInline(admin.TabularInline):
    model = IncidentResponse
    extra = 0
    readonly_fields = ["created_at"]
    autocomplete_fields = ["author"]


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin):
    list_display = [
        "id", "created_at", "predicted_label", "confidence", "response_status",
        "assigned_officer", "location_text", "source", "verification", "status",
    ]
    list_filter = ["status", "response_status", "predicted_label", "verification", "demo", "source"]
    search_fields = ["filename", "id", "location_text", "notes"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["user", "assigned_officer", "model"]
    inlines = [IncidentResponseInline]


@admin.register(IncidentResponse)
class IncidentResponseAdmin(admin.ModelAdmin):
    list_display = ["id", "incident", "action", "author", "created_at"]
    list_filter = ["action", "created_at"]
    search_fields = ["message", "incident__id", "author__email"]
    autocomplete_fields = ["incident", "author"]
    readonly_fields = ["created_at"]


@admin.register(NotifyAgency)
class NotifyAgencyAdmin(admin.ModelAdmin):
    list_display = ["name", "agency_type", "phone", "email", "barangay", "latitude", "longitude", "is_active", "updated_at"]
    list_filter = ["agency_type", "is_active"]
    search_fields = ["name", "contact_name", "phone", "email", "barangay", "address"]
    readonly_fields = ["created_at", "updated_at"]
