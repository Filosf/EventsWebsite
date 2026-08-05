from django.utils.functional import lazy
from django.utils.translation import get_language

ADMIN_LANGUAGES = ("ru", "en")


def current_admin_language() -> str:
    language = (get_language() or "ru").split("-", 1)[0]
    return language if language in ADMIN_LANGUAGES else "ru"


def _admin_text(russian: str, english: str) -> str:
    return english if current_admin_language() == "en" else russian


admin_text = lazy(_admin_text, str)
