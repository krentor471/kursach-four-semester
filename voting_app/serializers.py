from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import Category, Nomination, Vote
from .services import cast_vote, model_errors_to_dict


class CategorySerializer(serializers.ModelSerializer):
    """Сериализатор категории с вычисляемой статистикой."""

    nominations_count = serializers.SerializerMethodField()
    total_votes = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "slug",
            "image",
            "is_active",
            "is_featured",
            "priority",
            "color",
            "created_at",
            "updated_at",
            "nominations_count",
            "total_votes",
            "average_rating",
            "user_role",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        """Проверяет название на уровне сериализатора."""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Название должно содержать минимум 3 символа.")
        return value

    def validate(self, attrs: dict) -> dict:
        """Проверяет зависимые поля категории."""
        is_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        is_featured = attrs.get("is_featured", getattr(self.instance, "is_featured", False))
        if is_featured and not is_active:
            raise serializers.ValidationError(
                {"is_featured": "Неактивную категорию нельзя сделать рекомендуемой."}
            )
        return attrs

    def get_nominations_count(self, obj: Category) -> int:
        """Возвращает количество номинаций из аннотации или ORM."""
        return obj.get_nominations_count()

    def get_total_votes(self, obj: Category) -> int:
        """Возвращает количество голосов из аннотации или ORM."""
        return obj.get_total_votes()

    def get_average_rating(self, obj: Category) -> float:
        """Возвращает средний рейтинг категории."""
        return round(float(getattr(obj, "average_rating", 0) or 0), 2)

    def get_user_role(self, obj: Category) -> str:
        """Пример передачи данных через context: роль текущего пользователя."""
        return self.context.get("user_role", "anonymous")


class NominationSerializer(serializers.ModelSerializer):
    """Сериализатор номинации с результатами голосования."""

    votes_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True)
    is_voting_open = serializers.SerializerMethodField()
    can_current_user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Nomination
        fields = [
            "id",
            "title",
            "subtitle",
            "description",
            "short_description",
            "category",
            "category_name",
            "voting_start",
            "voting_end",
            "is_active",
            "created_at",
            "updated_at",
            "votes_count",
            "average_rating",
            "is_voting_open",
            "can_current_user_vote",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_title(self, value: str) -> str:
        """Проверяет название на уровне поля сериализатора."""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Название должно содержать минимум 2 символа.")
        return value

    def validate(self, attrs: dict) -> dict:
        """Проверяет даты голосования на уровне всего объекта."""
        start = attrs.get("voting_start", getattr(self.instance, "voting_start", None))
        end = attrs.get("voting_end", getattr(self.instance, "voting_end", None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"voting_end": "Дата окончания должна быть позже даты начала."}
            )
        return attrs

    def get_votes_count(self, obj: Nomination) -> int:
        """Возвращает количество голосов."""
        return obj.get_votes_count()

    def get_average_rating(self, obj: Nomination) -> float:
        """Возвращает среднюю оценку."""
        return round(obj.get_average_rating(), 2)

    def get_is_voting_open(self, obj: Nomination) -> bool:
        """Показывает, открыт ли период голосования."""
        return obj.is_voting_open()

    def get_can_current_user_vote(self, obj: Nomination) -> bool:
        """Показывает право текущего пользователя голосовать."""
        request = self.context.get("request")
        return bool(request and obj.user_can_vote(request.user))


class VoteSerializer(serializers.ModelSerializer):
    """Сериализатор голоса текущего пользователя."""

    nomination_title = serializers.CharField(source="nomination.title", read_only=True)
    category_name = serializers.CharField(source="nomination.category.name", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Vote
        fields = [
            "id",
            "nomination",
            "nomination_title",
            "category_name",
            "user",
            "user_username",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = ["user", "created_at"]

    def validate_rating(self, value: int) -> int:
        """Проверяет оценку."""
        if not 1 <= int(value) <= 5:
            raise serializers.ValidationError("Рейтинг должен быть от 1 до 5.")
        return value

    def validate_comment(self, value: str) -> str:
        """Проверяет длину комментария."""
        if len(value) > 1000:
            raise serializers.ValidationError("Комментарий не может быть длиннее 1000 символов.")
        return value

    def validate(self, attrs: dict) -> dict:
        """Проверяет, что голосование активно для выбранной номинации."""
        nomination = attrs.get("nomination", getattr(self.instance, "nomination", None))
        if nomination and not nomination.is_voting_open(timezone.now()):
            raise serializers.ValidationError(
                {"nomination": "Голосование закрыто или номинация неактивна."}
            )
        return attrs

    def create(self, validated_data: dict) -> Vote:
        """Создает голос от имени текущего пользователя."""
        request = self.context["request"]
        try:
            vote, _ = cast_vote(
                nomination=validated_data["nomination"],
                user=request.user,
                rating=validated_data["rating"],
                comment=validated_data.get("comment", ""),
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(model_errors_to_dict(error)) from error
        return vote
