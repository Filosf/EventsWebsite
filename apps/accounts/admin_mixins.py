from .permissions import can_manage_content, role_for


class RoleBasedAdminMixin:
    def has_module_permission(self, request):
        return role_for(request.user) is not None

    def has_view_permission(self, request, obj=None):
        return role_for(request.user) is not None

    def has_add_permission(self, request, obj=None):
        return can_manage_content(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_content(request.user)

    def has_delete_permission(self, request, obj=None):
        return can_manage_content(request.user)
