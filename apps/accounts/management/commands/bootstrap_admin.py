import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the first administrator from ADMIN_EMAIL and ADMIN_PASSWORD."

    def handle(self, *args, **options):
        email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not email or not password:
            raise CommandError("Set ADMIN_EMAIL and ADMIN_PASSWORD before running bootstrap_admin.")

        users = get_user_model()
        existing = users.objects.filter(email__iexact=email).first()
        if existing:
            if existing.is_active and existing.is_staff and existing.is_superuser:
                self.stdout.write(self.style.WARNING("Administrator already exists; password was not changed."))
                return
            raise CommandError("A non-administrator user with this email already exists.")

        candidate = users(username=email, email=email, is_active=True, is_staff=True, is_superuser=True)
        try:
            validate_password(password, candidate)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        users.objects.create_superuser(username=email, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Administrator {email} was created."))
