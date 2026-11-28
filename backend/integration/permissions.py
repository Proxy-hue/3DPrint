from rest_framework import permissions

from .contracts import ApiClientPrincipal


class HasApiScope(permissions.BasePermission):
    message = "Недостаточно прав для выполнения операции интеграционного API."

    def has_permission(self, request, view) -> bool:
        required_scope = getattr(view, "required_scope", None)
        user = request.user
        if not isinstance(user, ApiClientPrincipal) or not user.is_authenticated:
            return False
        if required_scope is None:
            return True
        return user.has_scope(required_scope)
