from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from .health import healthcheck

urlpatterns = [
    path("healthz/", healthcheck, name="healthcheck"),
    path("", RedirectView.as_view(pattern_name="admin:events_event_changelist", permanent=False), name="home"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", RedirectView.as_view(pattern_name="admin:events_event_changelist", permanent=False), name="admin_home"),
    path("admin/events/", include("apps.events.admin_urls")),
    path("admin/", admin.site.urls),
    path("", include("apps.events.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
