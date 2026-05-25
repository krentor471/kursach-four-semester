import re
from datetime import datetime
from typing import Any

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from simple_history.models import HistoricalRecords


HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class Category(models.Model):
    """Раздел голосования: например, фильмы, книги или проекты студентов."""

    name = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    slug = models.SlugField(max_length=120, blank=True, allow_unicode=True, verbose_name="Slug")
    image = models.ImageField(
        upload_to="categories/",
        blank=True,
        null=True,
        verbose_name="Изображение",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    is_featured = models.BooleanField(default=False, verbose_name="Рекомендуемая")
    priority = models.PositiveIntegerField(default=0, verbose_name="Приоритет")
    color = models.CharField(max_length=7, default="#0078d4", verbose_name="Цвет")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["-priority", "-created_at"]
        db_table = "voting_category"
        indexes = [
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["priority"]),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Проверяет бизнес-правила категории до сохранения."""
        errors: dict[str, str] = {}
        if len(self.name.strip()) < 3:
            errors["name"] = "Название должно содержать минимум 3 символа."
        if self.color and not HEX_COLOR_RE.match(self.color):
            errors["color"] = "Цвет должен быть в формате HEX, например #0078d4."
        if self.priority > 100:
            errors["priority"] = "Приоритет должен быть от 0 до 100."
        if self.is_featured and not self.is_active:
            errors["is_featured"] = "Неактивную категорию нельзя рекомендовать."
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Создает slug и запускает полную валидацию модели."""
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)[:120]
        self.full_clean()
        super().save(*args, **kwargs)

    def get_total_votes(self) -> int:
        """Возвращает количество голосов по всем номинациям категории."""
        annotated_value = getattr(self, "total_votes", None)
        if annotated_value is not None:
            return int(annotated_value)
        return Vote.objects.filter(nomination__category=self).count()

    def get_nominations_count(self) -> int:
        """Возвращает количество номинаций в категории."""
        annotated_value = getattr(self, "nominations_count", None)
        if annotated_value is not None:
            return int(annotated_value)
        return self.nominations.count()


class Nomination(models.Model):
    """Участник голосования внутри категории."""

    title = models.CharField(max_length=200, verbose_name="Название")
    subtitle = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Подзаголовок",
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    short_description = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Краткое описание",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="nominations",
        verbose_name="Категория",
    )
    voting_start = models.DateTimeField(
        default=timezone.now,
        verbose_name="Начало голосования",
    )
    voting_end = models.DateTimeField(
        default=timezone.now,
        verbose_name="Окончание голосования",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Номинация"
        verbose_name_plural = "Номинации"
        ordering = ["-created_at"]
        db_table = "voting_nomination"
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["voting_start", "voting_end"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.category.name})"

    def clean(self) -> None:
        """Проверяет сроки голосования и связь с активной категорией."""
        errors: dict[str, str] = {}
        if len(self.title.strip()) < 2:
            errors["title"] = "Название должно содержать минимум 2 символа."
        if self.voting_end and self.voting_start and self.voting_end <= self.voting_start:
            errors["voting_end"] = "Дата окончания должна быть позже даты начала."
        if self.category_id and not self.category.is_active and self.is_active:
            errors["category"] = "Активная номинация не может быть в неактивной категории."
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Запускает валидацию перед сохранением номинации."""
        self.full_clean()
        super().save(*args, **kwargs)

    def is_voting_open(self, at: datetime | None = None) -> bool:
        """Проверяет, можно ли сейчас голосовать за номинацию."""
        current_time = at or timezone.now()
        return (
            self.is_active
            and self.category.is_active
            and self.voting_start <= current_time <= self.voting_end
        )

    def get_votes_count(self) -> int:
        """Возвращает число голосов за номинацию."""
        annotated_value = getattr(self, "votes_count", None)
        if annotated_value is not None:
            return int(annotated_value)
        return self.votes.count()

    def get_average_rating(self) -> float:
        """Возвращает среднюю оценку номинации."""
        annotated_value = getattr(self, "average_rating", None)
        if annotated_value is not None:
            return float(annotated_value or 0)
        result = self.votes.aggregate(value=models.Avg("rating"))
        return float(result["value"] or 0)

    def user_can_vote(self, user: User) -> bool:
        """Проверяет базовое право пользователя на голосование."""
        return bool(user and user.is_authenticated and self.is_voting_open())

    def close_if_expired(self) -> bool:
        """Закрывает номинацию, если срок голосования уже прошел."""
        if self.is_active and self.voting_end < timezone.now():
            self.is_active = False
            self.save(update_fields=["is_active", "updated_at"])
            return True
        return False


class Vote(models.Model):
    """Один голос пользователя за одну номинацию."""

    nomination = models.ForeignKey(
        Nomination,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name="Номинация",
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Рейтинг",
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Голос"
        verbose_name_plural = "Голоса"
        unique_together = ["nomination", "user"]
        ordering = ["-created_at"]
        db_table = "voting_vote"
        indexes = [
            models.Index(fields=["user", "nomination"]),
            models.Index(fields=["rating"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.nomination.title} ({self.rating})"

    def clean(self) -> None:
        """Проверяет бизнес-правила голосования."""
        errors: dict[str, str] = {}
        if not 1 <= int(self.rating) <= 5:
            errors["rating"] = "Рейтинг должен быть от 1 до 5."
        if len(self.comment) > 1000:
            errors["comment"] = "Комментарий не может быть длиннее 1000 символов."
        if self.nomination_id and not self.nomination.is_voting_open():
            errors["nomination"] = "Голосование закрыто или номинация неактивна."
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Запускает полную серверную валидацию перед записью голоса."""
        self.full_clean()
        super().save(*args, **kwargs)
