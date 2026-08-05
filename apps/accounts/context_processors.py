from django.urls import reverse

from .admin_i18n import current_admin_language
from .permissions import is_administrator


def admin_navigation(request):
    if not request.path.startswith("/admin/"):
        return {}

    language = current_admin_language()
    english = language == "en"
    context = {
        "admin_language": language,
        "admin_ui": {
            "site_title": "Event management" if english else "Управление мероприятиями",
            "navigation": "Main sections" if english else "Основные разделы",
            "interface_language": "Admin language" if english else "Язык админки",
            "switch_language": "Switch" if english else "Переключить",
            "event_pages": "Event pages" if english else "Страницы ивента",
            "preview": "Preview" if english else "Превью",
            "open_separately": "Open separately" if english else "Открыть отдельно",
            "preview_language": "Preview language" if english else "Язык превью",
            "copy_link": "Copy link" if english else "Скопировать ссылку",
            "copied": "Copied" if english else "Скопировано",
        },
    }
    if not getattr(request.user, "is_authenticated", False):
        return context

    path = request.path
    active = "users" if path.startswith("/admin/auth/user/") else "events"

    items = [
        {"key": "events", "label": "Events" if english else "Ивенты", "url": reverse("admin:events_event_changelist")},
    ]
    if is_administrator(request.user):
        items.append({"key": "users", "label": "Users" if english else "Пользователи", "url": reverse("admin:auth_user_changelist")})
    context.update({"admin_navigation_items": items, "admin_navigation_active": active})
    return context
