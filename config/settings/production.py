from django.core.exceptions import ImproperlyConfigured

from config.storage import build_r2_storage

from .base import *  # noqa: F403

DEBUG = False
if SECRET_KEY == "dev-only-change-me":  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY must be set in production.")

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
}
OBJECT_STORAGE_REQUIRED = env.bool("OBJECT_STORAGE_REQUIRED", default=False)  # noqa: F405
r2_storage = build_r2_storage(os.environ, required=OBJECT_STORAGE_REQUIRED)  # noqa: F405
if r2_storage:
    STORAGES["default"] = r2_storage  # noqa: F405
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379/1"),  # noqa: F405
    }
}
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405
for external_host in (os.environ.get("RENDER_EXTERNAL_HOSTNAME", ""), os.environ.get("PUBLIC_DOMAIN", "")):  # noqa: F405
    parsed_host = urlparse(external_host if "://" in external_host else f"//{external_host}").hostname  # noqa: F405
    origin = f"https://{parsed_host}" if parsed_host else ""
    if origin and origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
