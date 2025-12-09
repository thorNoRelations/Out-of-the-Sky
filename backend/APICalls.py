import os
import time
import requests
from typing import Dict, Any
from django.conf import settings
from home.models import ApiUsage
from .models import APIRequestLog, AirportWeather
from django.db.models import F
from django.utils import timezone
from openai import OpenAI
import json
from typing import cast
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

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

##---------------AI API CALLS ---------------##
# ---------- OpenAI helpers JSON-only ----------

_OPENAI_CLIENT = None


def _get_openai_client() -> OpenAI:
    """
    Singleton-style OpenAI client using API key from environment or Django settings.
    """
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is not None:
        return _OPENAI_CLIENT

    api_key = os.environ.get("OPEN_AI_KEY", "").strip('"\'')
    if not api_key:
        api_key = getattr(settings, "OPEN_AI_KEY", "").strip('"\'') or None

    if not api_key:
        raise RuntimeError("OPEN_AI_KEY not configured in environment or settings.")

    _OPENAI_CLIENT = OpenAI(api_key=api_key)
    return _OPENAI_CLIENT


def _chat_json(system_prompt: str, user_prompt: str, model_env_name: str = "OPENAI_MODEL") -> Dict[str, Any]:
    client = _get_openai_client()
    model = os.environ.get(model_env_name, os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))

    messages = [
        cast(ChatCompletionSystemMessageParam, {
            "role": "system",
            "content": (
                "You are a backend JSON formatter for the Out of the Sky web app. "
                "Always respond with a single valid JSON object and nothing else. "
                "No explanations, no extra text."
            ),
        }),
        cast(ChatCompletionUserMessageParam, {
            "role": "user",
            "content": user_prompt,
        }),
    ]

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=messages,
    )

    content = response.choices[0].message.content
    return json.loads(content)


##----------- AI Flight Search ---------##

def ai_flight_search(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use OpenAI to normalize / interpret flight search input into a clean JSON result.

    Expected output JSON (example shape):

    {
      "flights": [
        {
          "flight_number": "",
          "airline": "",
          "origin": "",
          "origin_city": "",
          "destination": "",
          "destination_city": "",
          "status": "",
          "departure_time": "",
          "arrival_time": ""
        }
      ]
    }

    `filters` should contain any combination of:
    - flight_number
    - airline
    - origin_airport
    - destination_airport
    - status
    - free_text (optional natural-language query)
    """
    system_prompt = (
        "Return ONLY valid JSON with flights in this format:\n"
        "{ \"flights\": [ "
        "{ "
        "\"flight_number\": \"\", "
        "\"airline\": \"\", "
        "\"origin\": \"\", "
        "\"origin_city\": \"\", "
        "\"destination\": \"\", "
        "\"destination_city\": \"\", "
        "\"status\": \"on-time\", "
        "\"departure_time\": \"\", "
        "\"arrival_time\": \"\" "
        "} ] }"
    )

    user_payload = {
        "filters": filters,
    }

    user_prompt = (
        system_prompt
        + "\n\nUser flight search input (JSON):\n"
        + json.dumps(user_payload, ensure_ascii=False)
    )

    return _chat_json(system_prompt="", user_prompt=user_prompt, model_env_name="OPENAI_FLIGHTS_MODEL")

##----------- AI Delay Insights -----------##
def ai_delay_insights(location: str, weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use OpenAI to provide delay-risk insights for a location based on OpenWeather data.

    `location`  – user input city or airport (e.g. 'Denver', 'JFK').
    `weather_data` – raw JSON returned from OpenWeatherClient.fetch_city().

    Expected output JSON shape:

    {
      "location": "Denver International Airport",
      "delay_risk": "low",            # one of: low, medium, high
      "probability_percent": 10,
      "primary_causes": ["light snow", "reduced visibility"],
      "summary": "Weather is generally fine; only minor slowdowns are likely."
    }
    """
    system_prompt = (
        "You assess flight delay risk using current weather conditions. "
        "Return ONLY a JSON object with fields: "
        "location (string), delay_risk ('low'|'medium'|'high'), "
        "probability_percent (0-100 integer), "
        "primary_causes (array of short strings), "
        "summary (single short sentence, no fluff)."
    )

    user_payload = {
        "location": location,
        "openweather_payload": weather_data,
    }

    user_prompt = (
        system_prompt
        + "\n\nHere is the location and current OpenWeather data as JSON:\n"
        + json.dumps(user_payload, ensure_ascii=False)
    )

    return _chat_json(system_prompt="", user_prompt=user_prompt, model_env_name="OPENAI_DELAY_MODEL")

def update_airport_weather_from_openweather(
    airport_code: str,
    airport_name: str,
    city_query: str,
) -> AirportWeather:
    """
    Fetch current OpenWeather data, call AI delay insights, and
    update/create an AirportWeather row.
    """
    ow_client = OpenWeatherClient()
    ow = ow_client.fetch_city(city_query)  # e.g. "Denver,US"

    # --- Basic numeric fields (all imperial) ---
    temp_f = round(ow["main"]["temp"])  # OpenWeather already in F with units=imperial
    wind_mph = round(ow.get("wind", {}).get("speed", 0))

    visibility_meters = ow.get("visibility", 10000)
    visibility_miles = round(float(visibility_meters) / 1609.34, 1)

    # Map OpenWeather conditions to our choices
    main = ow["weather"][0]["main"].lower()
    if "thunder" in main:
        condition = "thunderstorm"
    elif "snow" in main:
        condition = "snow"
    elif "rain" in main:
        condition = "rain"
    elif "drizzle" in main:
        condition = "rain"
    elif "fog" in main or "mist" in main or "haze" in main:
        condition = "fog"
    elif "cloud" in main:
        condition = "cloudy"
    else:
        condition = "clear"

    # Rough precipitation chance from OpenWeather data if available
    precip_pct = 0
    if "rain" in ow:
        precip_pct = 60
    if "snow" in ow:
        precip_pct = max(precip_pct, 70)

    # --- Call AI for delay risk ---
    ai = ai_delay_insights(location=airport_name, weather_data=ow)

    delay_risk = ai.get("delay_risk", "low")        # "low"|"medium"|"high"
    probability = int(ai.get("probability_percent", 0))
    summary = ai.get("summary", "")

    # Simple mapping from probability ➜ estimated delay minutes
    if probability >= 80:
        est_min = 60
    elif probability >= 60:
        est_min = 45
    elif probability >= 40:
        est_min = 30
    elif probability >= 20:
        est_min = 15
    else:
        est_min = 0

    # --- Upsert AirportWeather row ---
    from django.utils import timezone
    forecast_time = timezone.now()

    obj, _ = AirportWeather.objects.update_or_create(
        airport_code=airport_code,
        forecast_time=forecast_time,
        defaults={
            "airport_name": airport_name,
            "condition": condition,
            "temperature": temp_f,
            "wind_speed": wind_mph,
            "visibility": visibility_miles,
            "precipitation_chance": precip_pct,
            "delay_risk": delay_risk if delay_risk in dict(AirportWeather.DELAY_RISK_CHOICES) else "low",
            "delay_probability": probability,
            "estimated_delay_minutes": est_min,
            "forecast_description": summary,
        },
    )

    return obj
