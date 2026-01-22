from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.contrib.auth import views as auth_views

def home(request):
    return HttpResponse('<h1>Система голосования</h1><p><a href="/api/web/">Категории</a> | <a href="/admin/">Админка</a></p>')

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('api/', include('voting_app.urls')),
]