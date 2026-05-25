from typing import Any

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Nomination, Vote


@transaction.atomic
def cast_vote(
    *,
    nomination: Nomination,
    user: User,
    rating: int,
    comment: str = "",
) -> tuple[Vote, bool]:
    """
    Создает или обновляет голос пользователя.

    Args:
        nomination: Номинация, за которую голосуют.
        user: Автор голоса.
        rating: Оценка от 1 до 5.
        comment: Необязательный комментарий.
    """
    locked_nomination = (
        Nomination.objects.select_for_update()
        .select_related("category")
        .get(pk=nomination.pk)
    )
    vote, created = Vote.objects.update_or_create(
        nomination=locked_nomination,
        user=user,
        defaults={"rating": rating, "comment": comment},
    )
    return vote, created


def model_errors_to_dict(error: ValidationError) -> dict[str, Any]:
    """Преобразует ValidationError Django в словарь для API-ответа."""
    if hasattr(error, "message_dict"):
        return error.message_dict
    return {"detail": error.messages}
