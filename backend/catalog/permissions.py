from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешает чтение всем (даже неавторизованным),
    а изменение (POST, PUT, DELETE) — только администраторам.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user
                    and request.user.is_authenticated
                    and request.user.role == 'ADMIN')
