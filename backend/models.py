from django.db import models


class APIRequestLog(models.Model):
    """Tracks every outbound OpenWeather call."""
    provider = models.CharField(max_length=64, db_index=True, default="openweathermap")
    endpoint = models.CharField(max_length=128, db_index=True)
    status_code = models.IntegerField()
    bytes = models.IntegerField(null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "created_at"], name="ix_provider_created"),
            models.Index(fields=["provider", "endpoint"], name="ix_provider_endpoint"),
        ]

    def __str__(self):
        return f"{self.provider} {self.endpoint} {self.status_code} @ {self.created_at:%Y-%m-%d %H:%M:%S}"


class AirportWeather(models.Model):
    """
    Stores the most recent OpenWeather payload for a given lookup key
    (we use the exact query string normalized).
    """
    providerSource = models.CharField(max_length=64, db_index=True, default="openweathermap")
    key = models.CharField(max_length=128, unique=True, db_index=True)  # e.g. "denver,us"
    conditionsJson = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.providerSource}:{self.key}"
