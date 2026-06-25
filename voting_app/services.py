from typing import Any

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Nomination, Vote


@transaction.atomic
def cast_vote(
    *,
    nomination: Nomination | int,
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
    nomination_pk = nomination if isinstance(nomination, int) else nomination.pk
    locked_nomination = (
        Nomination.objects.select_for_update()
        .select_related("category")
        .get(pk=nomination_pk)
    )
    rating = int(rating)
    if not 1 <= rating <= 5:
        raise ValidationError({"rating": "Рейтинг должен быть от 1 до 5."})
    if len(comment) > 1000:
        raise ValidationError({"comment": "Комментарий не может быть длиннее 1000 символов."})
    if not locked_nomination.is_voting_open():
        raise ValidationError({"nomination": "Голосование закрыто или номинация неактивна."})

    vote = Vote.objects.filter(nomination=locked_nomination, user=user).first()
    created = vote is None
    if created:
        vote = Vote(
            nomination=locked_nomination,
            user=user,
            rating=rating,
            comment=comment,
        )
        vote.save(skip_full_clean=True)
    else:
        vote.nomination = locked_nomination
        vote.rating = rating
        vote.comment = comment
        vote.save(update_fields=["rating", "comment"], skip_full_clean=True)
    return vote, created


def model_errors_to_dict(error: ValidationError) -> dict[str, Any]:
    """Преобразует ValidationError Django в словарь для API-ответа."""
    if hasattr(error, "message_dict"):
        return error.message_dict
    return {"detail": error.messages}
