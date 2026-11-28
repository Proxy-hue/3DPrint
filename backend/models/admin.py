from django.contrib import admin

from .models import ModelVersion, Order, PrintModel, ValidationResultRecord


@admin.register(PrintModel)
class PrintModelAdmin(admin.ModelAdmin):
    list_display = ("original_name", "owner", "format", "size", "status", "created_at")
    list_filter = ("format", "status")
    search_fields = ("original_name", "owner__username", "owner__email")


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = (
        "print_model",
        "version",
        "file_name",
        "format",
        "size_bytes",
        "volume_cm3",
        "is_current",
        "created_at",
    )
    list_filter = ("format", "is_current")
    search_fields = ("file_name", "storage_key")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ValidationResultRecord)
class ValidationResultRecordAdmin(admin.ModelAdmin):
    list_display = ("model_version", "verdict", "needs_support", "created_at")
    list_filter = ("verdict", "needs_support")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "model", "status", "equipment_compatible", "created_at")
    list_filter = ("status", "equipment_compatible")
