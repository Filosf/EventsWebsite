import csv
import hashlib

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from .models import Registration


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR") if settings.TRUST_X_FORWARDED_FOR else None
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _ip_hash(request) -> str:
    ip = client_ip(request)
    if not ip:
        return ""
    return hashlib.sha256(f"{settings.SECRET_KEY}:{ip}".encode()).hexdigest()


def response_cookie_name(event) -> str:
    return f"event_response_{event.pk}"


def existing_registration(*, event, cleaned_data, response_token=""):
    email = cleaned_data.get("email", "").strip().lower()
    phone = cleaned_data.get("phone", "").strip()
    query = Q()
    if email:
        query |= Q(email__iexact=email)
    if phone:
        query |= Q(phone=phone)
    if email or phone:
        return event.registrations.filter(query).order_by("-created_at").first()

    full_name = cleaned_data.get("full_name", "").strip()
    if not full_name or not response_token:
        return None
    return event.registrations.filter(edit_token=response_token, full_name__iexact=full_name).first()


@transaction.atomic
def submit_registration(*, event, form, request) -> Registration:
    registration = form.save(commit=False)
    registration.event = event
    registration.ip_hash = _ip_hash(request)
    registration.user_agent = request.META.get("HTTP_USER_AGENT", "")[:1024]
    registration.save()
    return registration


class _Echo:
    def write(self, value):
        return value


def iter_registrations_csv(event, registrations=None):
    writer = csv.writer(_Echo())
    yield "\ufeff"
    yield writer.writerow(["created_at", "full_name", "email", "phone", "attendance_status", "additional_guests", "comment"])
    rows = registrations if registrations is not None else event.registrations.order_by("created_at")
    iterator = rows.iterator(chunk_size=1000) if hasattr(rows, "iterator") else rows
    for registration in iterator:
        yield writer.writerow(
            [
                registration.created_at.isoformat(),
                _safe_csv_cell(registration.full_name),
                _safe_csv_cell(registration.email),
                _safe_csv_cell(registration.phone),
                registration.attendance_status,
                registration.guest_count,
                _safe_csv_cell(registration.comment),
            ]
        )


def export_registrations_csv(event, registrations=None) -> str:
    return "".join(iter_registrations_csv(event, registrations))


def _safe_csv_cell(value: str) -> str:
    if value and value[0] in {"=", "+", "-", "@"}:
        return "'" + value
    return value
