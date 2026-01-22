from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db import models
from django.db.models import Q, Count, Avg
from .models import Category, Nomination, Vote
from .serializers import CategorySerializer, NominationSerializer, VoteSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related().prefetch_related('nominations', 'nominations__votes')
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['is_active', 'is_featured']
    search_fields = ['name', 'description']
    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.nominations.exists():
            return Response(
                {'error': 'Нельзя удалить категорию с номинациями'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def popular(self, request):
        categories = Category.objects.filter(
            Q(is_active=True) & Q(nominations__isnull=False)
        ).annotate(
            nominations_count=Count('nominations')
        ).filter(nominations_count__gt=0).distinct()
        
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search_complex(self, request):
        query = request.query_params.get('q', '')
        if query:
            categories = Category.objects.filter(
                (Q(name__icontains=query) | Q(description__icontains=query)) &
                Q(is_active=True) & ~Q(nominations__isnull=True)
            ).distinct()
        else:
            categories = Category.objects.none()
        
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def featured_with_votes(self, request):
        """Сложный запрос: рекомендуемые категории с голосами, исключая неактивные"""
        categories = Category.objects.filter(
            (Q(is_featured=True) | Q(priority__gte=5)) &
            Q(nominations__votes__isnull=False) &
            ~Q(is_active=False)
        ).annotate(
            total_votes=Count('nominations__votes'),
            avg_rating=Avg('nominations__votes__rating')
        ).filter(total_votes__gt=0).distinct()
        
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def toggle_featured(self, request, pk=None):
        """Переключить статус рекомендуемой категории"""
        category = self.get_object()
        category.is_featured = not category.is_featured
        category.save()
        
        return Response({
            'message': f'Категория {category.name} теперь {"рекомендуемая" if category.is_featured else "обычная"}',
            'is_featured': category.is_featured
        })

class NominationViewSet(viewsets.ModelViewSet):
    queryset = Nomination.objects.select_related('category').prefetch_related('votes', 'votes__user')
    serializer_class = NominationSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['title', 'description']
    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.votes.exists():
            return Response(
                {'error': 'Нельзя удалить номинацию с голосами'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        queryset = Nomination.objects.select_related('category').prefetch_related('votes', 'votes__user')
        active_only = self.request.query_params.get('active_only')
        if active_only == 'true':
            queryset = queryset.filter(
                Q(is_active=True) & Q(category__is_active=True)
            )
        return queryset

    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        nomination = self.get_object()
        rating = request.data.get('rating')
        comment = request.data.get('comment', '')
        
        if not rating or not (1 <= int(rating) <= 5):
            return Response({'error': 'Rating must be between 1 and 5'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        vote, created = Vote.objects.update_or_create(
            nomination=nomination,
            user=request.user,
            defaults={'rating': rating, 'comment': comment}
        )
        
        serializer = VoteSerializer(vote)
        return Response(serializer.data, 
                       status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def top_rated(self, request):
        """Сложный запрос: топ номинаций с высоким рейтингом и комментариями"""
        nominations = Nomination.objects.filter(
            (Q(votes__rating__gte=4) | Q(category__is_featured=True)) &
            Q(votes__comment__isnull=False) &
            ~Q(votes__comment__exact='') &
            Q(is_active=True)
        ).annotate(
            avg_rating=Avg('votes__rating'),
            votes_count=Count('votes')
        ).filter(
            avg_rating__gte=3.5,
            votes_count__gte=1
        ).distinct().order_by('-avg_rating')
        
        serializer = self.get_serializer(nominations, many=True)
        return Response(serializer.data)

class VoteViewSet(viewsets.ModelViewSet):
    serializer_class = VoteSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['nomination', 'rating']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Vote.objects.select_related('user', 'nomination', 'nomination__category').filter(user=self.request.user)
        high_rating = self.request.query_params.get('high_rating')
        if high_rating == 'true':
            queryset = queryset.filter(
                Q(rating__gte=4) & ~Q(comment__exact='')
            )
        return queryset
    
    @action(detail=False, methods=['get'])
    def my_controversial_votes(self, request):
        """Сложный запрос: мои спорные голоса (высокий/низкий рейтинг с комментариями)"""
        votes = Vote.objects.filter(
            user=request.user
        ).filter(
            (Q(rating=1) | Q(rating=5)) &
            ~Q(comment__exact='') &
            Q(nomination__is_active=True)
        ).select_related('nomination', 'nomination__category')
        
        serializer = self.get_serializer(votes, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response(
                {'error': 'Можно удалять только свои голоса'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)