from django.apps import AppConfig

from apps.accounts.admin_i18n import admin_text


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"
    verbose_name = admin_text("Ивенты", "Events")

    def ready(self):
        from . import signals  # noqa: F401
