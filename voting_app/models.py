from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.utils import timezone
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords

class Category(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    slug = models.SlugField(max_length=120, blank=True, verbose_name="Slug")
    image = models.ImageField(upload_to='categories/', blank=True, null=True, verbose_name="Изображение")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    is_featured = models.BooleanField(default=False, verbose_name="Рекомендуемая")
    priority = models.PositiveIntegerField(default=0, verbose_name="Приоритет")
    color = models.CharField(max_length=7, default='#0078d4', verbose_name="Цвет")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['-created_at']
        db_table = 'voting_category'

    def __str__(self):
        return self.name

    def clean(self):
        if len(self.name) < 3:
            raise ValidationError('Название должно содержать минимум 3 символа')
        if self.color and not self.color.startswith('#'):
            raise ValidationError('Цвет должен быть в формате HEX (#RRGGBB)')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        self.full_clean()
        super().save(*args, **kwargs)

    def get_total_votes(self):
        return sum(nomination.votes.count() for nomination in self.nominations.all())

class Nomination(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название")
    subtitle = models.CharField(max_length=200, blank=True, default='', verbose_name="Подзаголовок")
    description = models.TextField(blank=True, verbose_name="Описание")
    short_description = models.CharField(max_length=500, blank=True, default='', verbose_name="Краткое описание")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='nominations', verbose_name="Категория")
    voting_start = models.DateTimeField(default=timezone.now, verbose_name="Начало голосования")
    voting_end = models.DateTimeField(default=timezone.now, verbose_name="Окончание голосования")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Номинация"
        verbose_name_plural = "Номинации"
        ordering = ['-created_at']
        db_table = 'voting_nomination'

    def __str__(self):
        return f"{self.title} ({self.category.name})"

    def clean(self):
        if len(self.title) < 2:
            raise ValidationError('Название должно содержать минимум 2 символа')
        if self.voting_end and self.voting_start and self.voting_end <= self.voting_start:
            raise ValidationError('Дата окончания должна быть позже даты начала')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_average_rating(self):
        votes = self.votes.all()
        if votes:
            return sum(vote.rating for vote in votes) / len(votes)
        return 0

class Vote(models.Model):
    nomination = models.ForeignKey(Nomination, on_delete=models.CASCADE, related_name='votes', verbose_name="Номинация")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Рейтинг"
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Голос"
        verbose_name_plural = "Голоса"
        unique_together = ['nomination', 'user']
        ordering = ['-created_at']
        db_table = 'voting_vote'

    def __str__(self):
        return f"{self.user.username} - {self.nomination.title} ({self.rating}★)"

    def clean(self):
        if not (1 <= self.rating <= 5):
            raise ValidationError('Рейтинг должен быть от 1 до 5')
        if len(self.comment) > 1000:
            raise ValidationError('Комментарий не может быть длиннее 1000 символов')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)