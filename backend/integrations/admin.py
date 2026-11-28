from django import forms
from django.contrib import admin, messages

from .contracts import ALL_SCOPES
from .models import (
    ApiClient,
    IntegrationOrderFacts,
    IntegrationStatusEvent,
    generate_api_key,
)
from .services import revoke_api_client, rotate_api_client_key


class ApiClientAdminForm(forms.ModelForm):
    scopes = forms.MultipleChoiceField(
        label="Области доступа (scopes)",
        choices=[(scope, scope) for scope in ALL_SCOPES],
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    class Meta:
        model = ApiClient
        fields = ("name", "scopes", "is_active")


@admin.register(ApiClient)
class ApiClientAdmin(admin.ModelAdmin):
    form = ApiClientAdminForm
    list_display = ("name", "key_prefix", "scopes", "is_active", "last_used_at", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "key_prefix")
    readonly_fields = ("id", "key_prefix", "api_key_hash", "last_used_at", "created_at", "updated_at")
    actions = ("action_rotate_keys", "action_revoke_clients")

    def save_model(self, request, obj, form, change):
        if not change:
            raw_key, key_prefix, key_hash = generate_api_key()
            obj.key_prefix = key_prefix
            obj.api_key_hash = key_hash
            super().save_model(request, obj, form, change)
            messages.warning(
                request,
                f"API-ключ для «{obj.name}» создан (показывается только один раз): {raw_key}",
            )
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="Перевыпустить API-ключ для выбранных клиентов")
    def action_rotate_keys(self, request, queryset):
        for client in queryset:
            issued = rotate_api_client_key(client.pk)
            messages.warning(
                request,
                f"Новый API-ключ для «{issued.name}» (показывается один раз): {issued.raw_api_key}",
            )

    @admin.action(description="Отозвать выбранных интеграционных клиентов")
    def action_revoke_clients(self, request, queryset):
        count = 0
        for client in queryset:
            revoke_api_client(client.pk)
            count += 1
        messages.info(request, f"Отозвано интеграционных клиентов: {count}.")


@admin.register(IntegrationOrderFacts)
class IntegrationOrderFactsAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "printer_name",
        "actual_material_name",
        "actual_material_g",
        "actual_print_hours",
        "updated_by_client",
        "updated_at",
    )
    search_fields = ("order__number", "printer_name", "actual_material_name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(IntegrationStatusEvent)
class IntegrationStatusEventAdmin(admin.ModelAdmin):
    list_display = ("order", "event_type", "from_status", "to_status", "actor_client", "created_at")
    list_filter = ("event_type", "from_status", "to_status")
    search_fields = ("order__number", "reason")
    readonly_fields = (
        "id",
        "order",
        "actor_client",
        "event_type",
        "from_status",
        "to_status",
        "reason",
        "actual_data",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
