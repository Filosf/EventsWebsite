import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import salted_hmac

from .services import client_ip

logger = logging.getLogger(__name__)


def _rate_key(event_id: int, request, window_name: str, window_seconds: int) -> str:
    ip = client_ip(request) or "unknown"
    ip_key = salted_hmac("registration-rate-limit", ip).hexdigest()
    window = int(time.time() // window_seconds)
    return f"rsvp-rate:{event_id}:{ip_key}:{window_name}:{window}"


def _increment(key: str, timeout: int) -> int:
    if cache.add(key, 1, timeout=timeout):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return 1


def registration_rate_limited(*, event, request) -> bool:
    limits = (
        ("short", settings.REGISTRATION_RATE_LIMIT_WINDOW, settings.REGISTRATION_RATE_LIMIT_COUNT),
        ("daily", 24 * 60 * 60, settings.REGISTRATION_DAILY_LIMIT_COUNT),
    )
    try:
        return any(
            _increment(_rate_key(event.pk, request, name, seconds), seconds + 5) > count
            for name, seconds, count in limits
        )
    except Exception:
        logger.exception("Registration rate-limit cache is unavailable; allowing the request.")
        return False
