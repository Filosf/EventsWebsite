from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.accounts.admin_i18n import admin_text
from apps.common import TimeStampedModel

from .validators import IMAGE_VALIDATORS

SUPPORTED_LANGUAGE_CODES = ("ru", "en", "he")


class Event(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", admin_text("Черновик", "Draft")
        PUBLISHED = "published", admin_text("Опубликован", "Published")
        REGISTRATION_CLOSED = "registration_closed", admin_text("Регистрация закрыта", "Registration closed")
        COMPLETED = "completed", admin_text("Завершён", "Completed")
        ARCHIVED = "archived", admin_text("В архиве", "Archived")

    internal_name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(blank=True, null=True)
    registration_starts_at = models.DateTimeField(blank=True, null=True)
    registration_ends_at = models.DateTimeField(blank=True, null=True)
    timezone = models.CharField(max_length=64, default="Asia/Jerusalem")
    default_language = models.CharField(max_length=8, default="ru")
    supported_languages = models.JSONField(default=list)
    max_guests = models.PositiveIntegerField(default=10)
    allow_public_registration = models.BooleanField(default=True)
    require_email = models.BooleanField(default=False)
    require_phone = models.BooleanField(default=False)
    is_search_engine_visible = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_events")

    class Meta:
        ordering = ["-starts_at", "internal_name"]
        verbose_name = admin_text("ивент", "event")
        verbose_name_plural = admin_text("ивенты", "events")
        indexes = [
            models.Index(fields=["status", "starts_at"]),
            models.Index(fields=["slug"]),
        ]

    def clean(self) -> None:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValidationError({"timezone": "Enter a valid IANA time zone, for example Asia/Jerusalem."}) from None
        if self.default_language not in SUPPORTED_LANGUAGE_CODES:
            raise ValidationError({"default_language": "Unsupported default language."})
        languages = self.supported_languages or []
        if not languages:
            self.supported_languages = [self.default_language]
        unsupported = set(self.supported_languages) - set(SUPPORTED_LANGUAGE_CODES)
        if unsupported:
            raise ValidationError({"supported_languages": f"Unsupported languages: {', '.join(sorted(unsupported))}"})
        if self.default_language not in self.supported_languages:
            raise ValidationError({"default_language": "Default language must be supported by the event."})
        if self.ends_at and self.ends_at < self.starts_at:
            raise ValidationError({"ends_at": "End time cannot be earlier than start time."})
        if self.registration_starts_at and self.registration_ends_at and self.registration_ends_at < self.registration_starts_at:
            raise ValidationError({"registration_ends_at": "Registration end cannot be earlier than registration start."})

    def publish(self) -> None:
        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()

    @property
    def accepts_registrations(self) -> bool:
        now = timezone.now()
        if self.status != self.Status.PUBLISHED or not self.allow_public_registration:
            return False
        if self.registration_starts_at and now < self.registration_starts_at:
            return False
        return not self.registration_ends_at or now <= self.registration_ends_at

    @property
    def theme_settings(self):
        try:
            return self.theme
        except EventTheme.DoesNotExist:
            return EventTheme(event=self)

    def __str__(self) -> str:
        return self.internal_name


class EventTranslation(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=8)
    banner_image = models.ImageField(upload_to="events/banners/", blank=True, validators=IMAGE_VALIDATORS)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    location_name = models.CharField(max_length=255, blank=True)
    location_address = models.CharField(max_length=255, blank=True)
    location_description = models.TextField(blank=True)
    success_message = models.TextField(blank=True)
    decline_message = models.TextField(blank=True)
    registration_closed_message = models.TextField(blank=True)
    additional_information = models.TextField(blank=True)

    class Meta:
        verbose_name = admin_text("перевод ивента", "event translation")
        verbose_name_plural = admin_text("переводы ивента", "event translations")
        constraints = [
            models.UniqueConstraint(fields=["event", "language"], name="unique_event_translation_language"),
        ]

    def __str__(self) -> str:
        return f"{self.event} [{self.language}]"


class EventTheme(TimeStampedModel):
    class Mode(models.TextChoices):
        LIGHT = "light", admin_text("Светлая", "Light")
        DARK = "dark", admin_text("Тёмная", "Dark")

    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="theme")
    background_image = models.ImageField(upload_to="events/backgrounds/", blank=True, validators=IMAGE_VALIDATORS)
    logo_image = models.ImageField(upload_to="events/logos/", blank=True, validators=IMAGE_VALIDATORS)
    primary_color = models.CharField(max_length=7, default="#31572c")
    secondary_color = models.CharField(max_length=7, default="#b08968")
    background_color = models.CharField(max_length=7, default="#f8f7f3")
    text_color = models.CharField(max_length=7, default="#1f2933")
    button_color = models.CharField(max_length=7, default="#31572c")
    button_text_color = models.CharField(max_length=7, default="#ffffff")
    border_radius = models.PositiveSmallIntegerField(default=8)
    theme_mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.LIGHT)

    class Meta:
        verbose_name = admin_text("оформление ивента", "event appearance")
        verbose_name_plural = admin_text("оформление ивента", "event appearance")

    def __str__(self) -> str:
        return f"Theme for {self.event}"
