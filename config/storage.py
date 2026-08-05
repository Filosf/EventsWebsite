from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

R2_ENVIRONMENT_KEYS = (
    "R2_ENDPOINT_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_CUSTOM_DOMAIN",
)


def build_r2_storage(environment, *, required=False):
    values = {key: environment.get(key, "").strip() for key in R2_ENVIRONMENT_KEYS}
    configured = [key for key, value in values.items() if value]
    if not configured and not required:
        return None

    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ImproperlyConfigured(
            "Cloudflare R2 configuration is incomplete. Missing: " + ", ".join(missing)
        )

    endpoint_url = values["R2_ENDPOINT_URL"].rstrip("/")
    endpoint = urlparse(endpoint_url)
    if endpoint.scheme != "https" or not endpoint.netloc or endpoint.path not in {"", "/"}:
        raise ImproperlyConfigured("R2_ENDPOINT_URL must be an HTTPS S3 endpoint without a path.")

    custom_domain = values["R2_CUSTOM_DOMAIN"].removeprefix("https://").removeprefix("http://").rstrip("/")
    domain = urlparse(f"//{custom_domain}")
    if not domain.hostname or domain.path or domain.query or domain.fragment:
        raise ImproperlyConfigured("R2_CUSTOM_DOMAIN must contain only a hostname.")

    return {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": values["R2_ACCESS_KEY_ID"],
            "secret_key": values["R2_SECRET_ACCESS_KEY"],
            "bucket_name": values["R2_BUCKET_NAME"],
            "endpoint_url": endpoint_url,
            "region_name": "auto",
            "custom_domain": custom_domain,
            "querystring_auth": False,
            "file_overwrite": False,
            "default_acl": None,
            "object_parameters": {"CacheControl": "public, max-age=604800"},
        },
    }
