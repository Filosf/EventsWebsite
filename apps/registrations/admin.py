from django.contrib import admin

from apps.accounts.admin_mixins import RoleBasedAdminMixin
from apps.accounts.permissions import is_administrator
from apps.audit.services import log_action, snapshot

from .models import Registration


@admin.register(Registration)
class RegistrationAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = ["full_name", "event", "attendance_status", "guest_count", "created_at"]
    list_filter = ["attendance_status", "event"]
    search_fields = ["full_name", "email", "phone", "event__internal_name"]
    readonly_fields = ["edit_token", "ip_hash", "user_agent", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return is_administrator(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_administrator(request.user)

    def save_model(self, request, obj, form, change):
        previous = snapshot(Registration.objects.get(pk=obj.pk)) if change else {}
        super().save_model(request, obj, form, change)
        log_action(
            request=request,
            action="registration_updated" if change else "registration_created_by_admin",
            instance=obj,
            previous_data=previous,
        )

    def delete_model(self, request, obj):
        previous = snapshot(obj)
        log_action(request=request, action="registration_deleted", instance=obj, previous_data=previous, new_data={})
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)
