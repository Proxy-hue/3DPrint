from django.contrib import admin

from common.admin import ReadOnlyAdminMixin

from .models import Order, OrderEvent


@admin.register(Order)
class OrderAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Заказы только для просмотра.

    Статус и параметры заказа меняются через API и сервисы: так
    соблюдаются таблица переходов и журнал событий.
    """

    list_display = ('number', 'client', 'status', 'priority', 'technology',
                    'material', 'quantity', 'planned_date', 'created_at')
    list_filter = ('status', 'priority', 'technology')
    search_fields = ('number', 'client__email')
    date_hierarchy = 'created_at'
    list_select_related = ('client', 'technology', 'material')


@admin.register(OrderEvent)
class OrderEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('order', 'type', 'from_status', 'to_status', 'actor',
                    'created_at')
    list_filter = ('type',)
    search_fields = ('order__number',)
    list_select_related = ('order', 'actor')
