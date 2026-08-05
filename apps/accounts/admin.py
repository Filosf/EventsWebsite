from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied

from apps.audit.services import log_action, snapshot

from .admin_forms import (
    EmailAdminAuthenticationForm,
    StaffUserChangeForm,
    StaffUserCreationForm,
)
from .admin_i18n import admin_text
from .permissions import is_administrator

admin.site.enable_nav_sidebar = False
admin.site.site_header = admin_text("Управление мероприятиями", "Event management")
admin.site.site_title = admin_text("Администрирование", "Administration")
admin.site.index_title = admin_text("Управление", "Management")
admin.site.login_form = EmailAdminAuthenticationForm


admin.site.unregister(get_user_model())
admin.site.unregister(Group)


class AdministratorFilter(admin.SimpleListFilter):
    title = admin_text("Администратор", "Administrator")
    parameter_name = "administrator"

    def lookups(self, request, model_admin):
        return (("yes", admin_text("Да", "Yes")), ("no", admin_text("Нет", "No")))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(is_superuser=True)
        if self.value() == "no":
            return queryset.filter(is_superuser=False)
        return queryset


@admin.register(get_user_model())
class AdministrativeUserAdmin(UserAdmin):
    form = StaffUserChangeForm
    add_form = StaffUserCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (admin_text("Личные данные", "Personal information"), {"fields": ("first_name", "last_name")}),
        (
            admin_text("Доступ", "Access"),
            {
                "fields": ("is_active", "is_superuser"),
                "description": admin_text(
                    "Все пользователи являются сотрудниками. Администратор может управлять другими пользователями.",
                    "All users are staff members. An administrator can manage other users.",
                ),
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "first_name", "last_name", "is_superuser"),
            },
        ),
    )
    list_display = ("email", "first_name", "last_name", "administrator_status", "is_active")
    list_filter = (AdministratorFilter, "is_active")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    filter_horizontal = ()

    def has_module_permission(self, request):
        return is_administrator(request.user)

    def has_view_permission(self, request, obj=None):
        return is_administrator(request.user)

    def has_add_permission(self, request):
        return is_administrator(request.user)

    def has_change_permission(self, request, obj=None):
        return is_administrator(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_administrator(request.user) and obj != request.user

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def delete_queryset(self, request, queryset):
        if queryset.filter(pk=request.user.pk).exists():
            raise PermissionDenied
        super().delete_queryset(request, queryset)

    def get_readonly_fields(self, request, obj=None):
        return ("is_active", "is_superuser") if obj == request.user else ()

    @admin.display(boolean=True, description=admin_text("Администратор", "Administrator"), ordering="is_superuser")
    def administrator_status(self, obj):
        return obj.is_superuser

    def save_model(self, request, obj, form, change):
        previous = snapshot(get_user_model().objects.get(pk=obj.pk)) if change else {}
        obj.email = obj.email.lower()
        obj.username = obj.email
        obj.is_staff = True
        super().save_model(request, obj, form, change)
        log_action(
            request=request,
            action="admin_user_updated" if change else "admin_user_created",
            instance=obj,
            previous_data=previous,
        )
