"""Общие настройки и миксины Django admin.

Доступ в админку есть только у роли ADMIN (и суперпользователя):
спецификация 5.3.5. Менеджеры работают в АРМ менеджера (веб-интерфейс).
Заказы, расчёты, платежи и переписка в админке только для просмотра:
менять их можно лишь через сервисы с учётом статусной модели и журнала.
"""
from django.contrib import admin

from .permissions import ADMIN, get_role

admin.site.site_header = '3DPrint: панель администратора'
admin.site.site_title = '3DPrint'
admin.site.index_title = 'Справочники, пользователи, журнал изменений'


class AdminRoleMixin:
    """Полный доступ к разделу только у роли ADMIN."""

    @staticmethod
    def _allowed(request):
        return get_role(request.user) == ADMIN

    def has_module_permission(self, request):
        return self._allowed(request)

    def has_view_permission(self, request, obj=None):
        return self._allowed(request)

    def has_add_permission(self, request):
        return self._allowed(request)

    def has_change_permission(self, request, obj=None):
        return self._allowed(request)

    def has_delete_permission(self, request, obj=None):
        return self._allowed(request)


class ReadOnlyAdminMixin(AdminRoleMixin):
    """Раздел только для просмотра (роль ADMIN)."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
