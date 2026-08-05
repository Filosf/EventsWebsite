from functools import wraps

from django.core.exceptions import PermissionDenied


def role_for(user):
    if not getattr(user, "is_authenticated", False) or not user.is_active or not user.is_staff:
        return None
    return "admin" if user.is_superuser else "staff"


def is_administrator(user) -> bool:
    return role_for(user) == "admin"


def can_manage_content(user) -> bool:
    return role_for(user) is not None


def can_publish(user) -> bool:
    return role_for(user) is not None


def can_export(user) -> bool:
    return role_for(user) is not None


def role_required(check):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
