import hashlib
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.conf import settings
from django.db.models import Model, QuerySet
from django.forms.models import model_to_dict

from .models import AuditLog


def _json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Model):
        return str(value.pk)
    if isinstance(value, (QuerySet, list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, (date, datetime, Decimal, UUID)):
        return str(value)
    if hasattr(value, "name"):
        return value.name
    return value


def snapshot(instance) -> dict:
    return {key: _json_value(value) for key, value in model_to_dict(instance).items()}


def _ip_hash(request) -> str:
    ip = request.META.get("REMOTE_ADDR", "")
    if not ip:
        return ""
    source = f"{settings.SECRET_KEY}:{ip}".encode()
    return hashlib.sha256(source).hexdigest()


def log_action(*, request, action: str, instance, event=None, previous_data=None, new_data=None) -> AuditLog:
    related_event = event
    if related_event is None:
        related_event = instance if instance._meta.label_lower == "events.event" else getattr(instance, "event", None)
    return AuditLog.objects.create(
        event=related_event,
        user=request.user if getattr(request.user, "is_authenticated", False) else None,
        action=action,
        entity_type=instance._meta.label_lower,
        entity_id=str(instance.pk),
        previous_data=previous_data or {},
        new_data=new_data if new_data is not None else snapshot(instance),
        ip_hash=_ip_hash(request),
    )
