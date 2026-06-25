from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from voting_app.models import Category, Nomination, Vote


class Command(BaseCommand):
    """Creates stable demo data for course defense."""

    help = "Создает пользователей и данные для демонстрации курсовой работы."

    def handle(self, *args, **options):
        moderator_group, _ = Group.objects.get_or_create(name="moderator")
        User = get_user_model()

        accounts = [
            {
                "username": "admin",
                "password": "admin12345",
                "email": "admin@example.com",
                "is_staff": True,
                "is_superuser": True,
                "groups": [],
            },
            {
                "username": "moderator",
                "password": "moderator12345",
                "email": "moderator@example.com",
                "is_staff": False,
                "is_superuser": False,
                "groups": [moderator_group],
            },
            {
                "username": "user",
                "password": "user12345",
                "email": "user@example.com",
                "is_staff": False,
                "is_superuser": False,
                "groups": [],
            },
        ]

        for account in accounts:
            groups = account.pop("groups")
            password = account.pop("password")
            user, _ = User.objects.get_or_create(
                username=account["username"],
                defaults=account,
            )
            for field, value in account.items():
                setattr(user, field, value)
            user.is_active = True
            user.set_password(password)
            user.save()
            user.groups.set(groups)

        category, _ = Category.objects.get_or_create(
            name="Лучшие учебные проекты",
            defaults={
                "description": "Демонстрационная категория для защиты курсовой работы.",
                "is_active": True,
                "is_featured": True,
                "priority": 10,
                "color": "#0078d4",
            },
        )
        category.is_active = True
        category.is_featured = True
        category.priority = 10
        category.save()

        now = timezone.now()
        nominations = [
            ("Django Voting", "Сайт онлайн-голосований с API и ролями."),
            ("API Analytics", "Номинация для демонстрации статистики и фильтров."),
            ("Celery Notifications", "Номинация для демонстрации фоновых задач."),
        ]
        user = User.objects.get(username="user")
        for index, (title, description) in enumerate(nominations, start=1):
            nomination, _ = Nomination.objects.get_or_create(
                title=title,
                category=category,
                defaults={"description": description},
            )
            nomination.description = description
            nomination.is_active = True
            nomination.voting_start = now - timedelta(minutes=5)
            nomination.voting_end = now + timedelta(days=7)
            nomination.save()
            if index <= 2:
                Vote.objects.update_or_create(
                    nomination=nomination,
                    user=user,
                    defaults={
                        "rating": 5 if index == 1 else 4,
                        "comment": "Демонстрационный голос для статистики.",
                    },
                )

        self.stdout.write(self.style.SUCCESS("Демонстрационные данные готовы."))
        self.stdout.write("admin / admin12345")
        self.stdout.write("moderator / moderator12345")
        self.stdout.write("user / user12345")
