from rest_framework.permissions import SAFE_METHODS, BasePermission

from .auth_utils import can_manage_voting


class IsModeratorOrReadOnly(BasePermission):
    """Разрешает чтение всем авторизованным, изменение - модераторам и админам."""

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user
            and request.user.is_authenticated
            and can_manage_voting(request.user)
        )


class IsOwnerOrAdmin(BasePermission):
    """Разрешает владельцу голоса или администратору работать с объектом."""

    def has_object_permission(self, request, view, obj) -> bool:
        return bool(request.user and (request.user.is_staff or obj.user_id == request.user.id))
