"""Django admin: справочники, тарифы, оборудование, аудит (F-MGR-09, 10).

Доступ — только у роли ADMIN (и суперпользователя), спецификация 5.3.5.
Каждое изменение записывается в журнал аудита (до/после).
"""
from django.contrib import admin

from common.admin import AdminRoleMixin, ReadOnlyAdminMixin

from .audit import record, snapshot
from .models import (
    AuditLog, Color, DeliveryMethod, Material, PickupPoint, PostProcessing,
    Printer, QualityProfile, TariffVersion, Technology, Workshop,
)


class AuditMixin:
    """Пишет создание, изменение и удаление в журнал аудита (до/после)."""

    def save_model(self, request, obj, form, change):
        obj._audit_before = None
        if change:
            stored = self.model.objects.filter(pk=obj.pk).first()
            if stored is not None:
                obj._audit_before = snapshot(stored)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        # M2M сохраняются после save_model, поэтому запись — здесь.
        super().save_related(request, form, formsets, change)
        obj = form.instance
        record(
            request.user, obj,
            'UPDATE' if change else 'CREATE',
            getattr(obj, '_audit_before', None),
            snapshot(obj),
        )

    def delete_model(self, request, obj):
        pk, before = obj.pk, snapshot(obj)
        super().delete_model(request, obj)
        record(request.user, obj, 'DELETE', before, None, entity_id=pk)

    def delete_queryset(self, request, queryset):
        for obj in list(queryset):
            self.delete_model(request, obj)


class AuditedAdmin(AdminRoleMixin, AuditMixin, admin.ModelAdmin):
    """ModelAdmin справочника: доступ только ADMIN, изменения в аудите."""


@admin.register(Workshop)
class WorkshopAdmin(AuditedAdmin):
    list_display = ('name', 'is_main', 'address', 'is_active')
    search_fields = ('name', 'address')


@admin.register(Technology)
class TechnologyAdmin(AuditedAdmin):
    list_display = ('code', 'name', 'hourly_rate', 'setup_cost', 'is_active')
    search_fields = ('code', 'name')


@admin.register(QualityProfile)
class QualityProfileAdmin(AuditedAdmin):
    list_display = ('name', 'technology', 'layer_height_mm', 'flow_cm3_h',
                    'price_factor', 'is_active')
    list_filter = ('technology', 'is_active')
    list_select_related = ('technology',)


@admin.register(Color)
class ColorAdmin(AuditedAdmin):
    list_display = ('name', 'hex', 'is_transparent', 'is_active')


@admin.register(Material)
class MaterialAdmin(AuditedAdmin):
    list_display = ('name', 'price_per_gram', 'density',
                    'required_specialization', 'is_active')
    list_filter = ('technologies', 'is_active')
    search_fields = ('name',)
    filter_horizontal = ('technologies', 'colors')


@admin.register(PostProcessing)
class PostProcessingAdmin(AuditedAdmin):
    list_display = ('code', 'name', 'price', 'hours', 'is_active')
    filter_horizontal = ('incompatible_technologies',)


@admin.register(DeliveryMethod)
class DeliveryMethodAdmin(AuditedAdmin):
    list_display = ('name', 'type', 'price', 'days', 'is_active')


@admin.register(PickupPoint)
class PickupPointAdmin(AuditedAdmin):
    list_display = ('name', 'address', 'delivery_method', 'is_active')
    list_select_related = ('delivery_method',)


@admin.register(Printer)
class PrinterAdmin(AuditedAdmin):
    list_display = ('name', 'workshop', 'technology', 'specialization',
                    'status')
    list_filter = ('workshop', 'technology', 'specialization', 'status')
    list_select_related = ('workshop', 'technology')
    filter_horizontal = ('materials',)
    search_fields = ('name',)


@admin.register(TariffVersion)
class TariffVersionAdmin(AuditedAdmin):
    list_display = ('__str__', 'is_active', 'created_by', 'created_at')
    readonly_fields = ('created_by',)

    def get_readonly_fields(self, request, obj=None):
        # Параметры существующей версии не меняются: создаётся новая.
        base = super().get_readonly_fields(request, obj)
        return base + ('params',) if obj else base

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'entity_type',
                    'entity_id')
    list_filter = ('action', 'entity_type')
    search_fields = ('entity_id',)
