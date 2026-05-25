from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.urls import include, path


def home(request):
    """Главная страница со ссылками на основные разделы проекта."""
    return HttpResponse(
        '<h1>Система онлайн-голосования</h1>'
        '<p><a href="/api/web/">Категории</a> | '
        '<a href="/admin/">Админка</a> | '
        '<a href="/api/">API</a> | '
        '<a href="/silk/">Silk</a></p>'
    )


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("oauth/", include("social_django.urls", namespace="social")),
    path("silk/", include("silk.urls", namespace="silk")),
    path("api/", include("voting_app.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
