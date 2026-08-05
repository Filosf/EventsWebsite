from django.contrib import admin

from apps.accounts.admin_mixins import RoleBasedAdminMixin

from .models import EventPageView


@admin.register(EventPageView)
class EventPageViewAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = ["event", "language", "created_at"]
    list_filter = ["event", "language"]
    search_fields = ["event__internal_name", "path"]
    readonly_fields = ["visitor_key", "user_agent", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
