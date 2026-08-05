from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models.functions import Lower
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import activate
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.accounts.admin_i18n import admin_text, current_admin_language
from apps.accounts.permissions import can_export, is_administrator, role_for
from apps.analytics.services import (
    VISITOR_COOKIE,
    record_event_view,
    statistics_for_event,
    visitor_id_for_request,
)
from apps.audit.services import log_action, snapshot
from apps.registrations.admin_forms import RegistrationAdminEditForm
from apps.registrations.anti_abuse import registration_rate_limited
from apps.registrations.models import Registration
from apps.registrations.services import (
    existing_registration,
    iter_registrations_csv,
    response_cookie_name,
    submit_registration,
)

from .forms import RegistrationForm
from .i18n import interface_text
from .models import Event
from .services import translation_for


def _select_language(request, event: Event, requested_language: str | None) -> str:
    supported = event.supported_languages or [event.default_language]
    cookie_language = request.COOKIES.get("event_language")
    browser_language = request.LANGUAGE_CODE
    for candidate in [requested_language, cookie_language, browser_language, event.default_language]:
        if candidate in supported:
            return candidate
    return event.default_language


@xframe_options_sameorigin
def event_page(request, slug: str, language: str | None = None):
    event = get_object_or_404(Event.objects.prefetch_related("translations"), slug=slug)
    if event.status in {Event.Status.DRAFT, Event.Status.ARCHIVED} and not request.user.is_staff:
        raise Http404

    selected_language = _select_language(request, event, language)
    activate(selected_language)
    translation = translation_for(event, selected_language)
    ui = interface_text(selected_language)
    try:
        event_starts_at = event.starts_at.astimezone(ZoneInfo(event.timezone))
    except ZoneInfoNotFoundError:
        event_starts_at = event.starts_at
    visitor_id, is_new_visitor = visitor_id_for_request(request)
    if request.method == "GET" and not request.user.is_staff:
        record_event_view(event=event, request=request, visitor_id=visitor_id, language=selected_language)

    response_status = 200
    if request.method == "POST":
        form = RegistrationForm(request.POST, event=event, language=selected_language)
        if registration_rate_limited(event=event, request=request):
            form.add_error(None, ui["too_many_requests"])
            response_status = 429
        elif form.is_valid() and event.accepts_registrations:
            if existing_registration(
                event=event,
                cleaned_data=form.cleaned_data,
                response_token=request.COOKIES.get(response_cookie_name(event), ""),
            ):
                form.add_error(None, ui["duplicate_response"])
            else:
                registration = submit_registration(event=event, form=form, request=request)
                response = redirect("events:registration_thanks", language=selected_language, slug=event.slug, token=registration.edit_token)
                response.set_cookie("event_language", selected_language, max_age=60 * 60 * 24 * 365)
                response.set_cookie(
                    response_cookie_name(event),
                    str(registration.edit_token),
                    max_age=60 * 60 * 24 * 365,
                    httponly=True,
                    secure=not settings.DEBUG,
                    samesite="Lax",
                )
                return response
    else:
        form = RegistrationForm(event=event, language=selected_language)

    response = render(
        request,
        "events/event_page.html",
        {
            "event": event,
            "translation": translation,
            "form": form,
            "language": selected_language,
            "languages": [(code, label) for code, label in settings.LANGUAGES if code in (event.supported_languages or [])],
            "dir": "rtl" if selected_language == "he" else "ltr",
            "ui": ui,
            "event_starts_at": event_starts_at,
        },
        status=response_status,
    )
    response.set_cookie("event_language", selected_language, max_age=60 * 60 * 24 * 365)
    if is_new_visitor:
        response.set_cookie(VISITOR_COOKIE, visitor_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
    return response


def registration_thanks(request, language: str, slug: str, token: str):
    event = get_object_or_404(Event, slug=slug)
    registration = get_object_or_404(Registration, event=event, edit_token=token)
    if language not in (event.supported_languages or []):
        raise Http404
    translation = translation_for(event, language)
    message = translation.success_message
    if registration.attendance_status == Registration.Attendance.DECLINED and translation.decline_message:
        message = translation.decline_message
    return render(
        request,
        "events/thanks.html",
        {
            "event": event,
            "translation": translation,
            "language": language,
            "dir": "rtl" if language == "he" else "ltr",
            "ui": interface_text(language),
            "message": message,
        },
    )


def _statistics_ui():
    english = current_admin_language() == "en"
    return {
        "title": "Statistics" if english else "Статистика",
        "registrations": "Responses" if english else "Ответы",
        "attending": "Attending" if english else "Придут",
        "declined": "Declined" if english else "Не придут",
        "expected_guests": "Expected guests" if english else "Ожидается гостей",
        "page_views": "Page views" if english else "Просмотры страницы",
        "unique_visitors": "Unique visitors" if english else "Уникальные посетители",
        "export_csv": "Export CSV" if english else "Экспорт CSV",
        "guest_responses": "Guest responses" if english else "Ответы гостей",
        "guest": "Guest" if english else "Гость",
        "response": "Response" if english else "Ответ",
        "guests": "Additional guests" if english else "Доп. гости",
        "contact": "Contact" if english else "Контакты",
        "comment": "Comment" if english else "Комментарий",
        "submitted": "Submitted" if english else "Получен",
        "actions": "Actions" if english else "Действия",
        "edit": "Edit" if english else "Редактировать",
        "delete": "Delete" if english else "Удалить",
        "empty": "There are no responses yet." if english else "Ответов пока нет.",
        "previous": "Previous" if english else "Назад",
        "next": "Next" if english else "Далее",
        "page": "Page" if english else "Страница",
        "of": "of" if english else "из",
        "back_to_event": "Back to event" if english else "К ивенту",
        "save": "Save" if english else "Сохранить",
        "cancel": "Cancel" if english else "Отмена",
        "edit_response": "Edit response" if english else "Редактирование ответа",
        "delete_response": "Delete response" if english else "Удаление ответа",
        "delete_question": "Are you sure you want to delete this response?" if english else "Вы уверены, что хотите удалить этот ответ?",
        "delete_warning": "This action cannot be undone." if english else "Это действие нельзя отменить.",
        "confirm_delete": "Yes, delete" if english else "Да, удалить",
        "attending_value": "Attending" if english else "Придёт",
        "declined_value": "Declined" if english else "Не придёт",
        "filter_label": "Show" if english else "Показывать",
        "filter_all": "All responses" if english else "Все ответы",
        "filter_attending": "Attending only" if english else "Только тех, кто придёт",
        "filter_declined": "Declined only" if english else "Только тех, кто не придёт",
        "sort_label": "Sort by" if english else "Сортировать",
        "sort_newest": "Newest first" if english else "Сначала новые",
        "sort_name": "Name A-Z" if english else "Имя по алфавиту",
        "sort_attending": "Attending first" if english else "Сначала те, кто придёт",
        "sort_declined": "Declined first" if english else "Сначала те, кто не придёт",
        "sort_guests_asc": "Additional guests: low to high" if english else "Доп. гости: по возрастанию",
        "sort_guests_desc": "Additional guests: high to low" if english else "Доп. гости: по убыванию",
        "apply": "Apply" if english else "Применить",
        "shown": "shown" if english else "показано",
        "expected_guests_hint": (
            "Attending respondents plus their additional guests"
            if english
            else "Ответившие «приду» плюс их дополнительные гости"
        ),
    }


RESPONSE_FILTERS = {"all", Registration.Attendance.ATTENDING, Registration.Attendance.DECLINED}
RESPONSE_SORTS = {"newest", "name", "attending", "declined", "guests_asc", "guests_desc"}


def _response_options(request):
    status = request.POST.get("status") or request.GET.get("status") or "all"
    sort = request.POST.get("sort") or request.GET.get("sort") or "newest"
    page = request.POST.get("page") or request.GET.get("page") or ""
    return {
        "status": status if status in RESPONSE_FILTERS else "all",
        "sort": sort if sort in RESPONSE_SORTS else "newest",
        "page": page if page.isdigit() and int(page) > 0 else "",
    }


def _response_queryset(event, options):
    queryset = event.registrations.all()
    if options["status"] != "all":
        queryset = queryset.filter(attendance_status=options["status"])
    if options["sort"] == "name":
        return queryset.order_by(Lower("full_name"), "id")
    if options["sort"] == "attending":
        return queryset.order_by("attendance_status", Lower("full_name"), "id")
    if options["sort"] == "declined":
        return queryset.order_by("-attendance_status", Lower("full_name"), "id")
    if options["sort"] == "guests_asc":
        return queryset.order_by("guest_count", Lower("full_name"), "id")
    if options["sort"] == "guests_desc":
        return queryset.order_by("-guest_count", Lower("full_name"), "id")
    return queryset.order_by("-created_at", "-id")


def _statistics_return_url(event_id: int, options) -> str:
    url = reverse("event_admin:statistics", kwargs={"event_id": event_id})
    query = urlencode({key: value for key, value in options.items() if value})
    return f"{url}?{query}" if query else url


@staff_member_required
def event_statistics(request, event_id: int):
    if role_for(request.user) is None:
        raise PermissionDenied
    event = get_object_or_404(Event, id=event_id)
    ui = _statistics_ui()
    options = _response_options(request)
    paginator = Paginator(_response_queryset(event, options), 25)
    page_obj = paginator.get_page(options["page"])
    for registration in page_obj.object_list:
        registration.localized_attendance = (
            ui["attending_value"] if registration.attendance_status == Registration.Attendance.ATTENDING else ui["declined_value"]
        )
    return render(
        request,
        "admin/events/statistics.html",
        {
            "event": event,
            "stats": statistics_for_event(event),
            "stats_ui": ui,
            "page_obj": page_obj,
            "filtered_total": paginator.count,
            "can_manage_responses": is_administrator(request.user),
            "selected_status": options["status"],
            "selected_sort": options["sort"],
            "list_query": urlencode({"status": options["status"], "sort": options["sort"]}),
            "return_query": urlencode({"status": options["status"], "sort": options["sort"], "page": page_obj.number}),
            "status_options": [
                ("all", ui["filter_all"]),
                (Registration.Attendance.ATTENDING, ui["filter_attending"]),
                (Registration.Attendance.DECLINED, ui["filter_declined"]),
            ],
            "sort_options": [
                ("newest", ui["sort_newest"]),
                ("name", ui["sort_name"]),
                ("attending", ui["sort_attending"]),
                ("declined", ui["sort_declined"]),
                ("guests_asc", ui["sort_guests_asc"]),
                ("guests_desc", ui["sort_guests_desc"]),
            ],
            "title": f'{ui["title"]}: {event.internal_name}',
        },
    )


@staff_member_required
def registration_edit(request, event_id: int, registration_id: int):
    if not is_administrator(request.user):
        raise PermissionDenied
    event = get_object_or_404(Event, id=event_id)
    registration = get_object_or_404(Registration, id=registration_id, event=event)
    options = _response_options(request)
    previous = snapshot(registration) if request.method == "POST" else None
    form = RegistrationAdminEditForm(request.POST or None, instance=registration)
    if request.method == "POST" and form.is_valid():
        registration = form.save()
        log_action(request=request, action="registration_updated", instance=registration, previous_data=previous)
        messages.success(request, admin_text("Ответ обновлён.", "The response was updated."))
        return redirect(_statistics_return_url(event.id, options))
    ui = _statistics_ui()
    return render(
        request,
        "admin/events/registration_form.html",
        {
            "event": event,
            "registration": registration,
            "form": form,
            "stats_ui": ui,
            "list_options": options,
            "return_query": urlencode({key: value for key, value in options.items() if value}),
            "title": f'{ui["edit_response"]}: {registration.full_name}',
        },
    )


@staff_member_required
def registration_delete(request, event_id: int, registration_id: int):
    if not is_administrator(request.user):
        raise PermissionDenied
    event = get_object_or_404(Event, id=event_id)
    registration = get_object_or_404(Registration, id=registration_id, event=event)
    options = _response_options(request)
    if request.method == "POST":
        previous = snapshot(registration)
        log_action(request=request, action="registration_deleted", instance=registration, previous_data=previous, new_data={})
        registration.delete()
        messages.success(request, admin_text("Ответ удалён.", "The response was deleted."))
        return redirect(_statistics_return_url(event.id, options))
    ui = _statistics_ui()
    return render(
        request,
        "admin/events/registration_confirm_delete.html",
        {
            "event": event,
            "registration": registration,
            "stats_ui": ui,
            "list_options": options,
            "return_query": urlencode({key: value for key, value in options.items() if value}),
            "title": f'{ui["delete_response"]}: {registration.full_name}',
        },
    )


@staff_member_required
def registrations_export(request, event_id: int):
    if not can_export(request.user):
        raise PermissionDenied
    event = get_object_or_404(Event, id=event_id)
    options = _response_options(request)
    content = iter_registrations_csv(event, _response_queryset(event, options))
    log_action(
        request=request,
        action="registrations_exported",
        instance=event,
        new_data={"status": options["status"], "sort": options["sort"]},
    )
    response = StreamingHttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{event.slug}-registrations.csv"'
    return response


def switch_language(request, slug: str, language: str):
    event = get_object_or_404(Event, slug=slug)
    if language not in (event.supported_languages or []):
        raise Http404
    response = redirect(reverse("events:event_page_language", kwargs={"language": language, "slug": slug}))
    response.set_cookie("event_language", language, max_age=60 * 60 * 24 * 365)
    return response
