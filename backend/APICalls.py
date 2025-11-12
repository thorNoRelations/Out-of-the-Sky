import os
import time
import requests
from typing import Dict, Any
from django.conf import settings
from dotenv import load_dotenv

from home.models import ApiUsage
from .models import APIRequestLog, AirportWeather
from django.db.models import F
from django.utils import timezone

load_dotenv()

PROVIDER = "openweathermap"
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

def _norm_key(q: str) -> str:
    return (q or "").strip().lower()


class OpenWeatherClient:
    """Minimal client that ONLY calls OpenWeather /weather, logs usage, and saves the latest payload."""
    def __init__(self):
        self.units = getattr(settings, "WEATHER_UNITS", os.getenv("WEATHER_UNITS"))
        if not self.api_key:
            raise RuntimeError("OPENWEATHER_API_KEY not configured")

    def fetch_city(self, q: str) -> Dict[str, Any]:
        if not q or not q.strip():
            raise ValueError("q (city) is required, e.g. 'Denver,US'")

        params = {"q": q.strip(), "appid": self.api_key, "units": self.units}
        t0 = time.time()
        resp = requests.get(BASE_URL, params=params, timeout=15)
        latency_ms = int((time.time() - t0) * 1000)

        content_len = None
        try:
            content_len = int(resp.headers.get("Content-Length", "0"))
        except Exception:
            pass

        endpoint = "/data/2.5/weather"
        if resp.status_code != 200:
            error_message = None
            try:
                j = resp.json()
                error_message = j.get("message")
            except Exception:
                error_message = (resp.text or "")[:500] if resp.text else None

            APIRequestLog.objects.create(
                provider=PROVIDER,
                endpoint=endpoint,
                status_code=resp.status_code,
                bytes=content_len,
                latency_ms=latency_ms,
                error_message=error_message,
            )
            bump_api_usage(PROVIDER)
            raise RuntimeError(f"OpenWeather error {resp.status_code}: {error_message or 'unknown error'}")

        data = resp.json()
        APIRequestLog.objects.create(
            provider=PROVIDER,
            endpoint=endpoint,
            status_code=resp.status_code,
            bytes=content_len,
            latency_ms=latency_ms,
        )
        bump_api_usage(PROVIDER)
        # -- NEW: save latest payload for weather map --
        key = _norm_key(q)
        obj, _ = AirportWeather.objects.get_or_create(
            providerSource=PROVIDER, key=key, defaults={"conditionsJson": data}
        )
        obj.conditionsJson = data
        obj.save()

        return data

 ###### API USAGE #######
def _yyyymmdd_now():
     return timezone.now().strftime("%Y%m%d")

def bump_api_usage(provider: str):
    ymd = _yyyymmdd_now()
    obj, created = ApiUsage.objects.get_or_create(provider=provider, yyyymmdd=ymd, defaults={"count": 0})
    # atomic increment
    ApiUsage.objects.filter(pk=obj.pk).update(count=F("count") + 1)
