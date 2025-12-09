import os
import time
import requests
from typing import Dict, Any
from django.conf import settings
from home.models import ApiUsage
from .models import APIRequestLog, AirportWeather
from django.db.models import F
from django.utils import timezone

PROVIDER = "openweathermap"
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


def _norm_key(q: str) -> str:
    return (q or "").strip().lower()


class OpenWeatherClient:
    """Minimal client that ONLY calls OpenWeather /weather, logs usage, and saves the latest payload."""

    def __init__(self):
        # Get API key directly from environment variable (same as settings.py)
        self.api_key = os.environ.get("OPENWEATHER_API_KEY", "").strip('"\'')

        # Fallback to Django settings if not in environment
        if not self.api_key:
            self.api_key = getattr(settings, 'OPENWEATHER_API_KEY', None)
            if self.api_key:
                self.api_key = self.api_key.strip('"\'')

        # Get units from environment or settings
        self.units = os.environ.get("WEATHER_UNITS",
                                    getattr(settings, 'WEATHER_UNITS', 'imperial')).strip('"\'')

        # Enhanced error message with debugging info
        if not self.api_key:
            env_keys = [k for k in os.environ.keys() if 'WEATHER' in k.upper() or 'OPEN' in k.upper()]
            error_msg = (
                f"❌ OPENWEATHER_API_KEY not configured!\n"
                f"\n"
                f"Configuration Status:\n"
                f"  - settings.OPENWEATHER_API_KEY exists: {hasattr(settings, 'OPENWEATHER_API_KEY')}\n"
                f"  - os.environ OPENWEATHER_API_KEY exists: {'OPENWEATHER_API_KEY' in os.environ}\n"
                f"  - Environment variables with WEATHER/OPEN: {env_keys}\n"
                f"\n"
                f"🔧 Fix this by:\n"
                f"  1. Check your .env file in Render has: OPENWEATHER_API_KEY=your_key_here\n"
                f"  2. Make sure there are NO quotes around the key value\n"
                f"  3. Redeploy your application on Render\n"
            )
            raise RuntimeError(error_msg)

        # Validate key format
        if len(self.api_key) < 20:
            raise RuntimeError(
                f"⚠️  OPENWEATHER_API_KEY seems invalid (too short: {len(self.api_key)} chars). "
                f"Check your Render environment variables."
            )

    def fetch_city(self, q: str) -> Dict[str, Any]:
        if not q or not q.strip():
            raise ValueError("q (city) is required, e.g. 'Denver,US'")

        params = {"q": q.strip(), "appid": self.api_key, "units": self.units}
        t0 = time.time()

        try:
            resp = requests.get(BASE_URL, params=params, timeout=15)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error calling OpenWeather API: {str(e)}")

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

            # Provide helpful error messages
            if resp.status_code == 401:
                raise RuntimeError(
                    f"❌ OpenWeather API Authentication Failed (401)\n"
                    f"Error: {error_message}\n"
                    f"\n"
                    f"This usually means:\n"
                    f"  - Your API key is invalid or expired\n"
                    f"  - Your API key hasn't been activated yet (wait 10 minutes after signup)\n"
                    f"\n"
                    f"Check your Render environment variables and ensure OPENWEATHER_API_KEY is correct."
                )
            else:
                raise RuntimeError(
                    f"OpenWeather API error {resp.status_code}: {error_message or 'unknown error'}"
                )

        data = resp.json()

        # Log successful request
        APIRequestLog.objects.create(
            provider=PROVIDER,
            endpoint=endpoint,
            status_code=resp.status_code,
            bytes=content_len,
            latency_ms=latency_ms,
        )
        bump_api_usage(PROVIDER)

        # Save latest payload for weather map
        key = _norm_key(q)
        obj, _ = AirportWeather.objects.get_or_create(
            providerSource=PROVIDER, key=key, defaults={"conditionsJson": data}
        )
        obj.conditionsJson = data
        obj.save()

        return data


def fetchOpenSkyFlights(bbox=None, icao24=None):
    """
    Fetch live flight data from OpenSky Network API
    bbox: tuple of (lat_min, lon_min, lat_max, lon_max)
    icao24: specific aircraft identifier
    """
    import requests

    base_url = "https://opensky-network.org/api/states/all"
    params = {}

    if bbox:
        params['lamin'] = bbox[0]
        params['lomin'] = bbox[1]
        params['lamax'] = bbox[2]
        params['lomax'] = bbox[3]

    if icao24:
        params['icao24'] = icao24

    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        # Return empty structure if API fails
        return {'time': None, 'states': []}


def _yyyymmdd_now():
    return timezone.now().strftime("%Y%m%d")


def bump_api_usage(provider: str):
    ymd = _yyyymmdd_now()
    obj, created = ApiUsage.objects.get_or_create(
        provider=provider, yyyymmdd=ymd, defaults={"count": 0}
    )
    # atomic increment
    ApiUsage.objects.filter(pk=obj.pk).update(count=F("count") + 1)
