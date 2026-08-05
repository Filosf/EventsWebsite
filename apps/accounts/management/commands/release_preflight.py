import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import checks
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Validate production settings and required release services."

    def handle(self, *args, **options):
        failures = []
        if settings.DEBUG:
            failures.append("DEBUG must be False.")
        if settings.SECRET_KEY == "dev-only-change-me" or len(settings.SECRET_KEY) < 50:
            failures.append("SECRET_KEY must be a strong production value.")
        public_hosts = {host for host in settings.ALLOWED_HOSTS if host not in {"localhost", "127.0.0.1", "web"}}
        if not public_hosts:
            failures.append("ALLOWED_HOSTS must contain the public domain.")
        if not settings.CSRF_TRUSTED_ORIGINS or not all(origin.startswith("https://") for origin in settings.CSRF_TRUSTED_ORIGINS):
            failures.append("CSRF_TRUSTED_ORIGINS must contain HTTPS origins.")
        if not settings.SECURE_SSL_REDIRECT:
            failures.append("SECURE_SSL_REDIRECT must be True.")
        if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
            failures.append("Session and CSRF cookies must be secure.")
        site_address = (
            os.environ.get("SITE_ADDRESS")
            or os.environ.get("RENDER_EXTERNAL_HOSTNAME")
            or os.environ.get("PUBLIC_DOMAIN", "")
        )
        if not site_address or site_address.startswith("http://") or site_address in {"localhost", "https://localhost"}:
            failures.append("SITE_ADDRESS must be the public HTTPS domain.")
        if getattr(settings, "OBJECT_STORAGE_REQUIRED", False):
            storage_backend = settings.STORAGES.get("default", {}).get("BACKEND")
            if storage_backend != "storages.backends.s3.S3Storage":
                failures.append("Cloudflare R2 must be configured as the default storage backend.")

        deployment_messages = checks.run_checks(include_deployment_checks=True, databases=["default"])
        failures.extend(str(message) for message in deployment_messages if message.level >= checks.WARNING)

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as error:  # noqa: BLE001 - preflight reports backend failures together
            failures.append(f"Database check failed: {error.__class__.__name__}.")
        try:
            cache.set("release-preflight", "ok", timeout=10)
            if cache.get("release-preflight") != "ok":
                failures.append("Cache read-after-write failed.")
        except Exception as error:  # noqa: BLE001 - cache backends raise implementation-specific errors
            failures.append(f"Cache check failed: {error.__class__.__name__}.")

        users = get_user_model()
        if not users.objects.filter(is_active=True, is_staff=True, is_superuser=True).exists():
            failures.append("At least one active administrator is required.")
        demo_admin = users.objects.filter(email__iexact="admin@example.com").first()
        if demo_admin and demo_admin.check_password("admin1"):
            failures.append("The demo administrator password must not be used in production.")

        if failures:
            raise CommandError("Release preflight failed:\n- " + "\n- ".join(failures))
        self.stdout.write(self.style.SUCCESS("Release preflight passed."))
