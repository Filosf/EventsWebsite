from django.db import transaction
from django.utils.text import slugify

from .models import Event, EventTheme, EventTranslation


def unique_event_slug(base: str) -> str:
    slug_base = slugify(base)[:48] or "event"
    slug = slug_base
    suffix = 2
    while Event.objects.filter(slug=slug).exists():
        slug = f"{slug_base}-{suffix}"
        suffix += 1
    return slug


@transaction.atomic
def create_event(*, created_by, internal_name, starts_at, default_language="ru", supported_languages=None) -> Event:
    event = Event.objects.create(
        created_by=created_by,
        internal_name=internal_name,
        slug=unique_event_slug(internal_name),
        starts_at=starts_at,
        default_language=default_language,
        supported_languages=supported_languages or [default_language],
    )
    EventTheme.objects.create(event=event)
    EventTranslation.objects.create(event=event, language=default_language, title=internal_name)
    return event


def translation_for(event: Event, language: str) -> EventTranslation:
    return (
        event.translations.filter(language=language).first()
        or event.translations.filter(language=event.default_language).first()
        or event.translations.first()
    )
