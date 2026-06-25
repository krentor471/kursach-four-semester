from django.contrib.auth.models import AnonymousUser, User


def get_user_role(user: User | AnonymousUser) -> str:
    """Returns the current user's voting role and caches it for one request."""
    if not user or not user.is_authenticated:
        return "anonymous"
    if user.is_staff:
        return "admin"

    cached_role = getattr(user, "_voting_role", None)
    if cached_role:
        return cached_role

    user._voting_role = (
        "moderator" if user.groups.filter(name="moderator").exists() else "voter"
    )
    return user._voting_role


def can_manage_voting(user: User | AnonymousUser) -> bool:
    """Checks whether the user can manage categories and nominations."""
    return get_user_role(user) in {"admin", "moderator"}
