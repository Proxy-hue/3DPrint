from django.contrib import admin

from .models import PrintModel


@admin.register(PrintModel)
class PrintModelAdmin(admin.ModelAdmin):
    list_display = ("original_name", "owner", "format", "size", "status", "created_at")
    list_filter = ("format", "status")
    search_fields = ("original_name", "owner__username", "owner__email")
