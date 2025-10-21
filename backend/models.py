
from django.db import models

class Flight(models.Model):
    flightNumber = models.CharField(max_length=20, db_index=True, null=True, blank=True)
    airline = models.CharField(max_length=40, null=True, blank=True)
    depIata = models.CharField(max_length=10, db_index=True, null=True, blank=True)
    arrIata = models.CharField(max_length=10, db_index=True, null=True, blank=True)
    status = models.CharField(max_length=20, null=True, blank=True)
    depTime = models.CharField(max_length=40, null=True, blank=True)
    arrTime = models.CharField(max_length=40, null=True, blank=True)
    lastUpdated = models.DateTimeField(auto_now=True)
    providerSource = models.CharField(max_length=40, db_index=True)
    rawJson = models.JSONField(null=True, blank=True)
    queryHash = models.CharField(max_length=64, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["flightNumber", "depIata", "arrIata", "providerSource"], name="ix_flights_composite"),
        ]

class AirportWeather(models.Model):
    icao = models.CharField(max_length=10, db_index=True, null=True, blank=True)
    iata = models.CharField(max_length=10, db_index=True, null=True, blank=True)
    observedAt = models.CharField(max_length=40, null=True, blank=True)
    forecastStart = models.CharField(max_length=40, null=True, blank=True)
    forecastEnd = models.CharField(max_length=40, null=True, blank=True)
    conditionsJson = models.JSONField(null=True, blank=True)
    providerSource = models.CharField(max_length=40, db_index=True)
    lastUpdated = models.DateTimeField(auto_now=True)
    key = models.CharField(max_length=40, db_index=True)  # icaoOrIata

class MapsGeo(models.Model):
    queryHash = models.CharField(max_length=64, db_index=True)
    resultJson = models.JSONField(null=True, blank=True)
    providerSource = models.CharField(max_length=40, db_index=True)
    lastUpdated = models.DateTimeField(auto_now=True)


from django.db import models

class ApiUsage(models.Model):
    provider = models.CharField(max_length=40, db_index=True)
    yyyymmdd = models.CharField(max_length=8, db_index=True)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ("provider", "yyyymmdd")
        indexes = [models.Index(fields=["provider", "yyyymmdd"])]

    def __str__(self):
        return f"{self.provider} {self.yyyymmdd}: {self.count}"

