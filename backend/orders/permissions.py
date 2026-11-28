"""Права доступа модуля orders поверх common.permissions (спецификация 5.3.5)."""
from common.permissions import (  # noqa: F401
    ADMIN, CLIENT, MANAGER, IsAdminRole, IsAnyRole, IsManagerOrAdmin, get_role, has_role,
)

IsClient = has_role(CLIENT)
IsClientOrManager = IsAnyRole
IsManager = IsManagerOrAdmin
