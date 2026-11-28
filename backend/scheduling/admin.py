from django.contrib import admin

from common.admin import ReadOnlyAdminMixin

from .models import Assignment


@admin.register(Assignment)
class AssignmentAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Назначения только для просмотра: создаются через orders/services."""

    list_display = ('order', 'printer', 'planned_start', 'planned_end',
                    'is_manual', 'is_current')
    list_filter = ('is_current', 'is_manual', 'printer')
    search_fields = ('order__number',)
    list_select_related = ('order', 'printer')
