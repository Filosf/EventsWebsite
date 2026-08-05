from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.SET_NULL, blank=True, null=True, related_name="audit_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="audit_logs")
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    previous_data = models.JSONField(default=dict, blank=True)
    new_data = models.JSONField(default=dict, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "запись журнала"
        verbose_name_plural = "журнал действий"
        indexes = [models.Index(fields=["event", "created_at"]), models.Index(fields=["action", "created_at"])]

    def __str__(self) -> str:
        return f"{self.action}: {self.entity_type} {self.entity_id}"
