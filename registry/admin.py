from django.contrib import admin

from .models import DatasetInfo, DatasetSplit, MLModel


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    list_display = ["name", "version", "preprocessing", "val_accuracy", "test_accuracy", "avg_inference_ms", "is_active"]
    list_filter = ["is_active", "preprocessing"]


@admin.register(DatasetSplit)
class DatasetSplitAdmin(admin.ModelAdmin):
    list_display = ["label", "split", "count"]
    list_filter = ["split"]


admin.site.register(DatasetInfo)
