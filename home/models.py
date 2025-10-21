# models.py
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

