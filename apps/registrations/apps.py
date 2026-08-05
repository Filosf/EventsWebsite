from django.apps import AppConfig

from apps.accounts.admin_i18n import admin_text


class RegistrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.registrations"
    verbose_name = admin_text("Регистрации", "Registrations")
