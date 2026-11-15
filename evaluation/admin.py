from django.contrib import admin

from .models import Evaluation, Misclassified


class MisclassifiedInline(admin.TabularInline):
    model = Misclassified
    extra = 0


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "model", "status", "processed", "total", "accuracy", "failed"]
    list_filter = ["status"]
    inlines = [MisclassifiedInline]
