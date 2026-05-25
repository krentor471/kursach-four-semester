from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import CategoryFilter, NominationFilter, VoteFilter
from .models import Category, Nomination, Vote
from .permissions import IsModeratorOrReadOnly, IsOwnerOrAdmin
from .serializers import CategorySerializer, NominationSerializer, VoteSerializer
from .services import cast_vote, model_errors_to_dict


class CategoryViewSet(viewsets.ModelViewSet):
    """API для категорий онлайн-голосований."""

    serializer_class = CategorySerializer
    filterset_class = CategoryFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["priority", "created_at", "nominations_count", "total_votes"]
    permission_classes = [IsAuthenticated, IsModeratorOrReadOnly]

    def get_queryset(self):
        """Возвращает категории с аннотациями, чтобы не считать статистику в цикле."""
        return (
            Category.objects.prefetch_related("nominations", "nominations__votes")
            .annotate(
                nominations_count=Count("nominations", distinct=True),
                total_votes=Count("nominations__votes", distinct=True),
                average_rating=Avg("nominations__votes__rating"),
            )
            .order_by("-priority", "-created_at")
        )

    def get_serializer_context(self) -> dict:
        """Передает в сериализатор роль пользователя через context."""
        context = super().get_serializer_context()
        user = self.request.user
        if user.is_staff:
            role = "admin"
        elif user.groups.filter(name="moderator").exists():
            role = "moderator"
        else:
            role = "voter"
        context["user_role"] = role
        return context

    def destroy(self, request, *args, **kwargs):
        """Запрещает удаление категории, если в ней есть номинации."""
        instance = self.get_object()
        if instance.nominations.exists():
            return Response(
                {"error": "Нельзя удалить категорию с номинациями."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def popular(self, request):
        """Возвращает активные категории, где уже есть номинации."""
        categories = self.get_queryset().filter(is_active=True, nominations_count__gt=0)
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def search_complex(self, request):
        """Пример Q-объектов: сложный поиск по названию или описанию."""
        query = request.query_params.get("q", "")
        categories = self.get_queryset().filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True,
            nominations_count__gt=0,
        ) if query else Category.objects.none()
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def featured_with_votes(self, request):
        """Возвращает рекомендуемые категории с голосами и средним рейтингом."""
        categories = self.get_queryset().filter(
            Q(is_featured=True) | Q(priority__gte=5),
            is_active=True,
            total_votes__gt=0,
        )
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def toggle_featured(self, request, pk=None):
        """Переключает статус рекомендуемой категории."""
        category = self.get_object()
        category.is_featured = not category.is_featured
        category.save(update_fields=["is_featured", "updated_at"])
        return Response({"is_featured": category.is_featured})


class NominationViewSet(viewsets.ModelViewSet):
    """API для номинаций и голосования."""

    serializer_class = NominationSerializer
    filterset_class = NominationFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "subtitle", "description", "category__name"]
    ordering_fields = ["created_at", "voting_start", "voting_end", "votes_count", "average_rating"]
    permission_classes = [IsAuthenticated, IsModeratorOrReadOnly]

    def get_queryset(self):
        """Возвращает номинации с select_related и агрегированной статистикой."""
        queryset = (
            Nomination.objects.select_related("category")
            .prefetch_related("votes", "votes__user")
            .annotate(
                votes_count=Count("votes", distinct=True),
                average_rating=Avg("votes__rating"),
            )
            .order_by("-created_at")
        )
        active_only = self.request.query_params.get("active_only")
        if active_only == "true":
            queryset = queryset.filter(is_active=True, category__is_active=True)
        return queryset

    def destroy(self, request, *args, **kwargs):
        """Запрещает удаление номинации, если за нее уже голосовали."""
        instance = self.get_object()
        if instance.votes.exists():
            return Response(
                {"error": "Нельзя удалить номинацию с голосами."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def vote(self, request, pk=None):
        """Создает или обновляет голос текущего пользователя."""
        nomination = self.get_object()
        data = request.data.copy()
        data["nomination"] = nomination.pk
        serializer = VoteSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            vote, created = cast_vote(
                nomination=nomination,
                user=request.user,
                rating=serializer.validated_data["rating"],
                comment=serializer.validated_data.get("comment", ""),
            )
        except DjangoValidationError as error:
            return Response(model_errors_to_dict(error), status=status.HTTP_400_BAD_REQUEST)
        return Response(
            VoteSerializer(vote, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def top_rated(self, request):
        """Возвращает активные номинации с высоким средним рейтингом."""
        nominations = self.get_queryset().filter(
            is_active=True,
            votes_count__gte=1,
            average_rating__gte=3.5,
        ).order_by("-average_rating", "-votes_count")
        serializer = self.get_serializer(nominations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def open_now(self, request):
        """Возвращает номинации, доступные для голосования сейчас."""
        now = timezone.now()
        nominations = self.get_queryset().filter(
            is_active=True,
            category__is_active=True,
            voting_start__lte=now,
            voting_end__gte=now,
        )
        serializer = self.get_serializer(nominations, many=True)
        return Response(serializer.data)


class VoteViewSet(viewsets.ModelViewSet):
    """API для голосов текущего пользователя."""

    serializer_class = VoteSerializer
    filterset_class = VoteFilter
    filter_backends = [DjangoFilterBackend]
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        """Обычный пользователь видит свои голоса, админ - все."""
        queryset = Vote.objects.select_related("user", "nomination", "nomination__category")
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        high_rating = self.request.query_params.get("high_rating")
        if high_rating == "true":
            queryset = queryset.filter(Q(rating__gte=4) & ~Q(comment__exact=""))
        return queryset

    def perform_create(self, serializer: VoteSerializer) -> None:
        """Сохраняет голос через сериализатор и сервисную бизнес-логику."""
        serializer.save()

    @action(detail=False, methods=["get"])
    def my_controversial_votes(self, request):
        """Возвращает мои крайние оценки с комментариями."""
        votes = self.get_queryset().filter(
            Q(rating=1) | Q(rating=5),
            ~Q(comment__exact=""),
            nomination__is_active=True,
        )
        serializer = self.get_serializer(votes, many=True)
        return Response(serializer.data)
