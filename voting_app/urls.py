from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, web_views

app_name = 'voting_app'

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet)
router.register(r'nominations', views.NominationViewSet)
router.register(r'votes', views.VoteViewSet, basename='vote')

urlpatterns = [
    path('', include(router.urls)),
    
    path('web/', web_views.category_list, name='category_list'),
    path('web/category/<int:pk>/', web_views.category_detail, name='category_detail'),
    path('web/category/create/', web_views.category_create, name='category_create'),
    path('web/category/<int:pk>/edit/', web_views.category_edit, name='category_edit'),
    path('web/category/<int:pk>/delete/', web_views.category_delete, name='category_delete'),
    path('web/category/<int:category_id>/nomination/create/', web_views.nomination_create, name='nomination_create'),
    path('web/nomination/<int:pk>/vote/', web_views.nomination_vote, name='nomination_vote'),
    path('web/nomination/<int:pk>/delete/', web_views.nomination_delete, name='nomination_delete'),
]