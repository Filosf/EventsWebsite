import hashlib

from django.core.exceptions import ImproperlyConfigured


def normalize_production_secret(secret):
    if secret == "dev-only-change-me" or len(secret) < 32 or len(set(secret)) < 5:  # noqa: S105
        raise ImproperlyConfigured("SECRET_KEY must be a strong production value.")
    if len(secret) < 50:
        return hashlib.sha512(secret.encode()).hexdigest()
    return secret
