from django.contrib import admin

from common.admin import ReadOnlyAdminMixin

from .models import Quote


@admin.register(Quote)
class QuoteAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Сметы только для просмотра; корректировка цены — через API."""

    list_display = ('id', 'order', 'total', 'adjustment', 'estimated_days',
                    'is_current', 'created_at')
    list_filter = ('is_current',)
    search_fields = ('order__number',)
    list_select_related = ('order',)
