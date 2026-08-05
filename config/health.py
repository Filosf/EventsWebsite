from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache


@never_cache
def healthcheck(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        cache_key = "healthcheck"
        cache.set(cache_key, "ok", timeout=10)
        if cache.get(cache_key) != "ok":
            raise RuntimeError("Cache read-after-write failed.")
    except Exception:  # noqa: BLE001 - any dependency failure means unhealthy
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
