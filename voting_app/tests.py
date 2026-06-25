from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Nomination, Vote
from .services import cast_vote
from .tasks import close_expired_nominations, send_voting_ending_soon_emails


def create_nomination(category: Category, **kwargs) -> Nomination:
    """Создает номинацию с открытым периодом голосования."""
    defaults = {
        "title": "Какой-то проект",
        "description": "Описание",
        "category": category,
        "voting_start": timezone.now() - timedelta(hours=1),
        "voting_end": timezone.now() + timedelta(days=1),
    }
    defaults.update(kwargs)
    return Nomination.objects.create(**defaults)


class BusinessValidationTests(TestCase):
    """Проверки бизнес-валидации моделей и сервиса."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="voter", password="pass")
        self.category = Category.objects.create(name="Проекты", description="Студенческие проекты")

    def test_category_name_must_be_long_enough(self) -> None:
        category = Category(name="AB")
        with self.assertRaises(ValidationError):
            category.full_clean()

    def test_category_color_must_be_hex(self) -> None:
        category = Category(name="Проекты", color="red")
        with self.assertRaises(ValidationError):
            category.full_clean()

    def test_nomination_end_must_be_after_start(self) -> None:
        now = timezone.now()
        nomination = Nomination(
            title="Проект",
            category=self.category,
            voting_start=now,
            voting_end=now,
        )
        with self.assertRaises(ValidationError):
            nomination.full_clean()

    def test_vote_is_rejected_after_voting_closed(self) -> None:
        nomination = create_nomination(
            self.category,
            voting_start=timezone.now() - timedelta(days=2),
            voting_end=timezone.now() - timedelta(days=1),
        )
        vote = Vote(nomination=nomination, user=self.user, rating=5)
        with self.assertRaises(ValidationError):
            vote.full_clean()

    def test_cast_vote_updates_existing_vote(self) -> None:
        nomination = create_nomination(self.category)
        vote, created = cast_vote(nomination=nomination, user=self.user, rating=4)
        self.assertTrue(created)

        updated_vote, updated_created = cast_vote(
            nomination=nomination,
            user=self.user,
            rating=2,
            comment="Передумал",
        )
        self.assertFalse(updated_created)
        self.assertEqual(vote.pk, updated_vote.pk)
        self.assertEqual(updated_vote.rating, 2)
        self.assertEqual(Vote.objects.count(), 1)


class VotingApiTests(APITestCase):
    """Проверки API, фильтров, аннотаций и прав."""

    def setUp(self) -> None:
        self.voter = User.objects.create_user(username="voter", password="pass")
        self.admin = User.objects.create_user(
            username="admin",
            password="pass",
            is_staff=True,
        )
        self.moderator_group = Group.objects.create(name="moderator")
        self.category = Category.objects.create(
            name="Кино",
            description="Голосование за фильмы",
            is_featured=True,
            priority=10,
        )
        self.nomination = create_nomination(self.category, title="Фильм")

    def test_anonymous_user_cannot_read_api(self) -> None:
        response = self.client.get(reverse("voting_app:category-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_voter_can_read_category_statistics(self) -> None:
        self.client.force_authenticate(self.voter)
        cast_vote(nomination=self.nomination, user=self.voter, rating=5)
        response = self.client.get(reverse("voting_app:category-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first_result = response.data["results"][0]
        self.assertEqual(first_result["total_votes"], 1)
        self.assertEqual(first_result["user_role"], "voter")

    def test_voter_cannot_create_category(self) -> None:
        self.client.force_authenticate(self.voter)
        response = self.client.post(
            reverse("voting_app:category-list"),
            {"name": "Музыка", "description": ""},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_category(self) -> None:
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("voting_app:category-list"),
            {"name": "Музыка", "description": "Исполнители"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_vote_action_creates_vote(self) -> None:
        self.client.force_authenticate(self.voter)
        url = reverse("voting_app:nomination-vote", args=[self.nomination.pk])
        response = self.client.post(url, {"rating": 5, "comment": "Отлично"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Vote.objects.get().rating, 5)

    def test_nomination_filter_by_open_now(self) -> None:
        self.client.force_authenticate(self.voter)
        response = self.client.get(
            reverse("voting_app:nomination-list"),
            {"voting_open": "true"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_top_rated_uses_annotations(self) -> None:
        self.client.force_authenticate(self.voter)
        cast_vote(nomination=self.nomination, user=self.voter, rating=5)
        response = self.client.get(reverse("voting_app:nomination-top-rated"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["average_rating"], 5.0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CeleryTaskTests(TestCase):
    """Проверки периодических задач Celery."""

    def setUp(self) -> None:
        self.admin = User.objects.create_user(
            username="admin",
            password="pass",
            is_staff=True,
            email="admin@example.com",
        )
        self.category = Category.objects.create(name="Проекты")

    def test_close_expired_nominations_task(self) -> None:
        nomination = create_nomination(
            self.category,
            voting_start=timezone.now() - timedelta(days=3),
            voting_end=timezone.now() - timedelta(days=1),
        )
        updated = close_expired_nominations()
        nomination.refresh_from_db()
        self.assertEqual(updated, 1)
        self.assertFalse(nomination.is_active)

    def test_send_ending_soon_email_task(self) -> None:
        create_nomination(
            self.category,
            title="Скоро финал",
            voting_end=timezone.now() + timedelta(hours=3),
        )
        sent = send_voting_ending_soon_emails()
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Скоро финал", mail.outbox[0].body)
