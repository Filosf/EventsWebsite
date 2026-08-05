from django.db import models

from apps.common import TimeStampedModel
from apps.events.models import Event


class EventPageView(TimeStampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="page_views")
    visitor_key = models.CharField(max_length=64)
    path = models.CharField(max_length=512)
    language = models.CharField(max_length=8, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        verbose_name = "просмотр страницы"
        verbose_name_plural = "просмотры страниц"
        indexes = [
            models.Index(fields=["event", "visitor_key"]),
            models.Index(fields=["event", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event} view {self.created_at:%Y-%m-%d %H:%M}"
