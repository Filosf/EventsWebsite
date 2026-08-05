from django.contrib import admin

from apps.accounts.permissions import is_administrator

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "entity_type", "entity_id", "event", "user"]
    list_filter = ["action", "entity_type", "created_at"]
    search_fields = ["entity_id", "event__internal_name", "user__username"]
    readonly_fields = ["event", "user", "action", "entity_type", "entity_id", "previous_data", "new_data", "ip_hash", "created_at"]

    def has_module_permission(self, request):
        return is_administrator(request.user)

    def has_view_permission(self, request, obj=None):
        return is_administrator(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
