import django_filters

from .models import Category, Nomination, Vote


class CategoryFilter(django_filters.FilterSet):
    """Фильтры категорий для DRF."""

    min_priority = django_filters.NumberFilter(field_name="priority", lookup_expr="gte")
    max_priority = django_filters.NumberFilter(field_name="priority", lookup_expr="lte")
    has_votes = django_filters.BooleanFilter(method="filter_has_votes")

    class Meta:
        model = Category
        fields = ["is_active", "is_featured", "min_priority", "max_priority", "has_votes"]

    def filter_has_votes(self, queryset, name: str, value: bool):
        """Фильтрует категории по наличию голосов."""
        if value:
            return queryset.filter(nominations__votes__isnull=False).distinct()
        return queryset.filter(nominations__votes__isnull=True).distinct()


class NominationFilter(django_filters.FilterSet):
    """Фильтры номинаций: категория, сроки и рейтинг."""

    started_after = django_filters.DateTimeFilter(field_name="voting_start", lookup_expr="gte")
    ends_before = django_filters.DateTimeFilter(field_name="voting_end", lookup_expr="lte")
    min_rating = django_filters.NumberFilter(method="filter_min_rating")
    max_rating = django_filters.NumberFilter(method="filter_max_rating")
    voting_open = django_filters.BooleanFilter(method="filter_voting_open")

    class Meta:
        model = Nomination
        fields = [
            "category",
            "is_active",
            "started_after",
            "ends_before",
            "min_rating",
            "max_rating",
            "voting_open",
        ]

    def filter_min_rating(self, queryset, name: str, value: float):
        """Оставляет номинации со средней оценкой не ниже значения."""
        return queryset.filter(average_rating__gte=value)

    def filter_max_rating(self, queryset, name: str, value: float):
        """Оставляет номинации со средней оценкой не выше значения."""
        return queryset.filter(average_rating__lte=value)

    def filter_voting_open(self, queryset, name: str, value: bool):
        """Фильтрует номинации по открытому периоду голосования."""
        now = self.request.timezone_now if hasattr(self.request, "timezone_now") else None
        if now is None:
            from django.utils import timezone

            now = timezone.now()
        lookup = {
            "is_active": True,
            "category__is_active": True,
            "voting_start__lte": now,
            "voting_end__gte": now,
        }
        return queryset.filter(**lookup) if value else queryset.exclude(**lookup)


class VoteFilter(django_filters.FilterSet):
    """Фильтры голосов текущего пользователя."""

    min_rating = django_filters.NumberFilter(field_name="rating", lookup_expr="gte")
    max_rating = django_filters.NumberFilter(field_name="rating", lookup_expr="lte")
    category = django_filters.NumberFilter(field_name="nomination__category_id")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Vote
        fields = [
            "nomination",
            "rating",
            "min_rating",
            "max_rating",
            "category",
            "created_after",
            "created_before",
        ]
