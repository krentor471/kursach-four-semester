from .auth_utils import can_manage_voting


def voting_permissions(request) -> dict:
    """Добавляет флаг управления голосованиями во все шаблоны."""
    return {"can_manage_voting": can_manage_voting(request.user)}
