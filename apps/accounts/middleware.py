from django.utils import translation

from .admin_i18n import ADMIN_LANGUAGES


class AdminLocaleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            language = (translation.get_language() or "ru").split("-", 1)[0]
            if language not in ADMIN_LANGUAGES:
                language = "ru"
            translation.activate(language)
            request.LANGUAGE_CODE = language
        return self.get_response(request)
