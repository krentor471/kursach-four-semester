def voting_permissions(request) -> dict:
    """Добавляет флаг управления голосованиями во все шаблоны."""
    user = request.user
    can_manage = bool(
        user.is_authenticated
        and (user.is_staff or user.groups.filter(name="moderator").exists())
    )
    return {"can_manage_voting": can_manage}
