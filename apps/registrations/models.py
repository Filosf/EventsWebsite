import uuid

from django.db import models

from apps.accounts.admin_i18n import admin_text
from apps.common import TimeStampedModel
from apps.events.models import Event


class Registration(TimeStampedModel):
    class Attendance(models.TextChoices):
        ATTENDING = "attending", "Attending"
        DECLINED = "declined", "Declined"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    full_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    attendance_status = models.CharField(max_length=16, choices=Attendance.choices)
    guest_count = models.PositiveIntegerField(default=0)
    comment = models.TextField(blank=True)
    edit_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = admin_text("регистрация", "registration")
        verbose_name_plural = admin_text("регистрации", "registrations")
        indexes = [
            models.Index(fields=["event", "attendance_status"]),
            models.Index(fields=["event", "created_at"]),
            models.Index(fields=["event", "email"]),
            models.Index(fields=["event", "phone"]),
            models.Index(fields=["edit_token"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} - {self.event}"
