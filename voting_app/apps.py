from django.apps import AppConfig


class VotingAppConfig(AppConfig):
    """Конфигурация приложения голосований."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "voting_app"
    verbose_name = "Система онлайн-голосования"
