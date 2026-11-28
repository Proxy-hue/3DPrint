"""Ролевые права доступа для DRF (S-SEC-02).

Роли хранятся в ``User.role``. Суперпользователь (createsuperuser)
приравнивается к роли ADMIN.
"""
from rest_framework.permissions import BasePermission

CLIENT = 'CLIENT'
MANAGER = 'MANAGER'
ADMIN = 'ADMIN'


def get_role(user):
    """Возвращает роль пользователя или None для анонимного."""
    if user is None or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ADMIN
    return getattr(user, 'role', None)


def has_role(*roles):
    """Фабрика permission-классов: доступ только перечисленным ролям."""
    allowed = frozenset(roles)

    class HasRole(BasePermission):
        def has_permission(self, request, view):
            return get_role(request.user) in allowed

    HasRole.__name__ = 'HasRole_' + '_'.join(sorted(allowed))
    return HasRole


IsAnyRole = has_role(CLIENT, MANAGER, ADMIN)
IsManagerOrAdmin = has_role(MANAGER, ADMIN)
IsAdminRole = has_role(ADMIN)
