from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Count
from django.utils import timezone

from .models import Nomination


@shared_task
def close_expired_nominations() -> int:
    """
    Периодическая задача Celery: закрывает голосования с истекшим сроком.

    Returns:
        Количество закрытых номинаций.
    """
    updated = Nomination.objects.filter(
        is_active=True,
        voting_end__lt=timezone.now(),
    ).update(is_active=False, updated_at=timezone.now())
    return updated


@shared_task
def send_voting_ending_soon_emails() -> int:
    """
    Периодическая задача Celery: отправляет модераторам письмо о скором завершении.

    Returns:
        Количество писем, переданных SMTP-серверу.
    """
    now = timezone.now()
    tomorrow = now + timedelta(days=1)
    nominations = (
        Nomination.objects.select_related("category")
        .annotate(votes_count=Count("votes"))
        .filter(is_active=True, voting_end__range=(now, tomorrow))
        .order_by("voting_end")
    )
    if not nominations.exists():
        return 0

    lines = [
        f"{nomination.title} / {nomination.category.name}: "
        f"до {timezone.localtime(nomination.voting_end):%d.%m.%Y %H:%M}, "
        f"голосов: {nomination.votes_count}"
        for nomination in nominations
    ]
    User = get_user_model()
    recipients = list(
        User.objects.filter(is_staff=True, email__isnull=False)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        return 0

    return send_mail(
        subject="Голосования завершаются в ближайшие 24 часа",
        message="\n".join(lines),
        from_email=None,
        recipient_list=recipients,
        fail_silently=False,
    )
