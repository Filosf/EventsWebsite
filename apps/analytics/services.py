import hashlib
import logging
import secrets

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.db.models.functions import Coalesce

from apps.registrations.models import Registration

from .models import EventPageView

VISITOR_COOKIE = "event_visitor"
logger = logging.getLogger(__name__)


def visitor_id_for_request(request) -> tuple[str, bool]:
    visitor_id = request.COOKIES.get(VISITOR_COOKIE, "")
    if 20 <= len(visitor_id) <= 128:
        return visitor_id, False
    return secrets.token_urlsafe(32), True


def _visitor_key(visitor_id: str) -> str:
    return hashlib.sha256(visitor_id.encode("utf-8")).hexdigest()


def record_event_view(*, event, request, visitor_id: str, language: str = "") -> None:
    visitor_key = _visitor_key(visitor_id)
    cache_key = f"event-view:{event.pk}:{visitor_key}"
    try:
        if not cache.add(cache_key, 1, timeout=settings.PAGE_VIEW_DEDUP_SECONDS):
            return
    except Exception:  # Analytics must remain available without cache.
        logger.warning("Page-view deduplication cache is unavailable.", exc_info=True)
    EventPageView.objects.create(
        event=event,
        visitor_key=visitor_key,
        path=request.path[:512],
        language=(language or getattr(request, "LANGUAGE_CODE", ""))[:8],
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1024],
    )


def statistics_for_event(event) -> dict:
    registrations = event.registrations.all()
    attending = registrations.filter(attendance_status=Registration.Attendance.ATTENDING)
    declined = registrations.filter(attendance_status=Registration.Attendance.DECLINED)
    views = event.page_views.all()
    attending_total = attending.count()
    additional_guests = attending.aggregate(total=Coalesce(Sum("guest_count"), 0))["total"]
    return {
        "registrations_total": registrations.count(),
        "attending_total": attending_total,
        "declined_total": declined.count(),
        "expected_guests": attending_total + additional_guests,
        "page_views": views.count(),
        "unique_visitors": views.values("visitor_key").distinct().count(),
    }
