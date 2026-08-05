from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        identifier = username or kwargs.get(user_model.USERNAME_FIELD)
        if identifier is None or password is None:
            return None

        identifier = identifier.strip()
        try:
            user = user_model._default_manager.get(email__iexact=identifier)
        except user_model.DoesNotExist:
            try:
                user = user_model._default_manager.get(username__iexact=identifier)
            except (user_model.DoesNotExist, user_model.MultipleObjectsReturned):
                user_model().set_password(password)
                return None
        except user_model.MultipleObjectsReturned:
            user_model().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
