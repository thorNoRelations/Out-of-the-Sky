from __future__ import annotations
import os, json, time, random, hashlib, logging
from typing import Any, Dict, Optional, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime, timezone as _tz

from dotenv import load_dotenv
load_dotenv()

import requests
from requests.auth import HTTPBasicAuth

from django.db import transaction, connection
from django.utils import timezone as dj_tz

from .models import Flight, AirportWeather, MapsGeo

from django.http import JsonResponse
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
import os

from django.urls import path
from django.db.models import F



"""
Conservative API client layer with cache-first semantics and daily budgets.
- Prefers cached rows from the project's SQLite (Django ORM) whenever possible.
- Obeys per-provider limits and backs off aggressively.
- Serves stale cache when budgets are exhausted or providers return errors.

This module is a drop-in replacement for APICalls.py; function signatures are kept
compatible where they existed before.
"""

logger = logging.getLogger("apiCalls")
logger.setLevel(logging.INFO)

# ------------------------------
# Configuration
# ------------------------------
# Default TTLs for fresh cache (seconds)
DEFAULT_TTLS = {
    "weather": 1800,  # 30 min (was 10). More conservative.
    "flight": 90,     # 1.5 min (was 30). Reduce chattiness yet remain timely.
    "geo": 86400,
}

# We will still accept stale cache for a bit if budgets are tight or provider errors occur.
# "serve-stale-while-error/budget" windows (seconds)
MAX_STALE = {
    "weather": 6 * 3600,   # up to 6h
    "flight": 10 * 60,     # up to 10m
    "geo": 7 * 86400,
}

# Daily budgets (conservative) — see provider docs/notes in repo docs.
# OpenWeatherMap: first 1000/day free — we cap at 900 to stay under.
# AviationWeather.gov: documented per-minute limits; no daily quota specified — set a soft daily cap.
# AviationStack (free): effectively 1 call / 61s -> ~1400/day theoretical; we'll cap at 1000 but also enforce per-61s.
# OpenSky anonymous: 400 credits/day.
DAILY_BUDGETS = {
    "openweathermap": 900,
    "aviationweather": 2000,   # soft cap; real limit is per-minute. Keep generous but enforce cache-first.
    "aviationstack": 1000,
    "opensky": 380,            # stay below 400/day
    # Add others if enabled
}

# Per-second token buckets tuned to be conservative relative to provider rules
class SimpleRateLimiter:
    def __init__(self, rate_per_sec: float = 1.0, capacity: int = 1):
        self.rate = rate_per_sec
        self.capacity = capacity
        self.tokens = capacity
        self.last = time.monotonic()

    def acquire(self, tokens: float = 1.0):
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        sleep_time = (tokens - self.tokens) / self.rate
        time.sleep(max(0, sleep_time))
        self.tokens = 0
        return True

# Create rate limiters per provider (very conservative values)
limiters = {
    # OpenWeather: plenty of room, but don't spam — ~2 rps burst 2
    "openweathermap": SimpleRateLimiter(rate_per_sec=2/1.0, capacity=2),
    # AviationWeather: docs say max 100/min and 1 req/min per thread; keep ~0.8 rps, burst 1
    "aviationweather": SimpleRateLimiter(rate_per_sec=0.8, capacity=1),
    # AviationStack free: 1 call every 61s -> ~0.0164 rps; enforce with capacity 1
    "aviationstack": SimpleRateLimiter(rate_per_sec=1/61.0, capacity=1),
    # OpenSky: not too chatty — 0.2 rps burst 1
    "opensky": SimpleRateLimiter(rate_per_sec=0.2, capacity=1),
    # Geo
    "openstreetmap": SimpleRateLimiter(rate_per_sec=0.5, capacity=1),
}

# ------------------------------
# Minimal usage ledger (SQLite via Django connection)
# ------------------------------
# We avoid migrations by creating a simple table on first use.

_SQL_CREATE = """
CREATE TABLE IF NOT EXISTS api_usage (
  provider TEXT NOT NULL,
  yyyymmdd TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(provider, yyyymmdd)
)
"""


def _today_key() -> str:
    return dj_tz.now().astimezone(_tz.utc).strftime("%Y%m%d")


def _ensure_usage_table():
    with connection.cursor() as cur:
        cur.execute(_SQL_CREATE)


def get_usage(provider: str) -> int:
    _ensure_usage_table()
    with connection.cursor() as cur:
        cur.execute("SELECT count FROM api_usage WHERE provider=%s AND yyyymmdd=%s", [provider, _today_key()])
        row = cur.fetchone()
        return int(row[0]) if row else 0


def add_usage(provider: str, n: int = 1):
    _ensure_usage_table()
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO api_usage(provider, yyyymmdd, count) VALUES (%s,%s,%s)\n"
            "ON CONFLICT(provider, yyyymmdd) DO UPDATE SET count = api_usage.count + excluded.count",
            [provider, _today_key(), n],
        )


def under_budget(provider: str) -> bool:
    budget = DAILY_BUDGETS.get(provider)
    if not budget:
        return True
    return get_usage(provider) < budget


# ------------------------------
# Helpers
# ------------------------------

def sha256Stable(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":")) if not isinstance(obj, str) else obj
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class ProviderResponse:
    data: Dict[str, Any]
    provider: str
    cache: str  # "hit" | "miss" | "stale"


class ProviderClient:
    baseUrl = ""; providerName = ""; category = ""

    def __init__(self):
        self.session = requests.Session()

    def buildUrl(self, path: str, params: Dict[str, Any]):
        return f"{self.baseUrl.rstrip('/')}/{path.lstrip('/')}", params

    # Core network method with budgets and backoff
    def safeRequest(self, method: str, url: str, params=None, headers=None, auth=None, timeout=10, maxRetries=3):
        # Budget gate
        if not under_budget(self.providerName):
            logger.warning("%s: daily budget exhausted; serving cache only", self.providerName)
            return {"error": "budget_exhausted"}

        limiter = limiters.get(self.providerName, SimpleRateLimiter())
        backoff = 1.0
        last_error = None
        for _ in range(maxRetries):
            try:
                limiter.acquire()
                resp = self.session.request(method=method, url=url, params=params, headers=headers, auth=auth, timeout=timeout)
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    last_error = RuntimeError(f"{self.providerName} HTTP {resp.status_code}")
                    time.sleep(backoff + random.random() * 0.25)
                    backoff = min(backoff * 2, 16)
                    continue
                resp.raise_for_status()
                try:
                    add_usage(self.providerName, 1)
                except Exception as e:
                    logger.debug("usage ledger write failed: %s", e)
                try:
                    return resp.json()
                except Exception:
                    return {"text": resp.text}
            except (requests.Timeout, requests.ConnectionError) as e:
                last_error = e
                time.sleep(backoff + random.random() * 0.25)
                backoff = min(backoff * 2, 16)
            except Exception as e:
                last_error = e
                break
        logger.warning("safeRequest degraded for %s: %s", self.providerName, last_error)
        return {"error": str(last_error) if last_error else "unknown_error"}

    # --------------- Cache plumbing ---------------
    def _get_cached(self, key: str, ttl: int, allow_stale: bool = False) -> Optional[ProviderResponse]:
        now = dj_tz.now()
        recency = lambda dt: (now - dt).total_seconds() if dt else 10**9

        if self.category == "geo":
            row = MapsGeo.objects.filter(queryHash=key, providerSource=self.providerName).first()
            if row:
                age = recency(row.lastUpdated)
                if age < ttl:
                    return ProviderResponse({"result": row.resultJson or {}}, self.providerName, "hit")
                if allow_stale and age < MAX_STALE["geo"]:
                    return ProviderResponse({"result": row.resultJson or {}}, self.providerName, "stale")

        elif self.category == "weather":
            row = AirportWeather.objects.filter(key=key, providerSource=self.providerName).first()
            if row:
                age = recency(row.lastUpdated)
                payload = {"weather": row.conditionsJson or {}}
                if age < ttl:
                    return ProviderResponse(payload, self.providerName, "hit")
                if allow_stale and age < MAX_STALE["weather"]:
                    return ProviderResponse(payload, self.providerName, "stale")

        elif self.category == "flight":
            row = Flight.objects.filter(queryHash=key, providerSource=self.providerName).first()
            if row:
                age = recency(row.lastUpdated)
                norm = {
                    "flightNumber": row.flightNumber,
                    "airline": row.airline,
                    "depIata": row.depIata,
                    "arrIata": row.arrIata,
                    "status": row.status,
                    "depTime": row.depTime,
                    "arrTime": row.arrTime,
                    "raw": row.rawJson or {},
                }
                if age < ttl:
                    return ProviderResponse(norm, self.providerName, "hit")
                if allow_stale and age < MAX_STALE["flight"]:
                    return ProviderResponse(norm, self.providerName, "stale")
        return None

    def getCachedOrFetch(self, cacheKey: str, ttlSeconds: int, fetchFn: Callable[[], Dict[str, Any]]):
        # Always try fresh cache first
        cached = self._get_cached(cacheKey, ttlSeconds, allow_stale=False)
        if cached:
            return cached

        # If over budget, return stale if available; otherwise, try the network once (safeRequest will fail fast on budget)
        allow_stale = not under_budget(self.providerName)
        if allow_stale:
            stale = self._get_cached(cacheKey, ttlSeconds, allow_stale=True)
            if stale:
                return stale

        # Attempt a network fetch
        raw = fetchFn()
        if isinstance(raw, dict) and raw.get("error"):
            # Provider error or budget-exhausted — try stale cache
            stale = self._get_cached(cacheKey, ttlSeconds, allow_stale=True)
            if stale:
                return stale
            # Fall through and return the error payload (normalized below)

        # Upsert DB with whatever we got (only if not an error)
        if not (isinstance(raw, dict) and raw.get("error")):
            try:
                self._upsert(cacheKey, raw)
            except Exception as e:
                logger.warning("cache upsert failed for %s: %s", self.providerName, e)

        return ProviderResponse(self._normalizeForReturn(raw), self.providerName, "miss")

    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        raise NotImplementedError

    # In APICalls.py (class ProviderClient)
    def _normalizeForReturn(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        # Ensure consistent shapes on cache *misses* to match tests
        if self.category == "weather":
            # Wrap whatever the provider returned (e.g., {"metar": ...}) under "weather"
            return {"weather": raw or {}}
        if self.category == "geo":
            # Your _get_cached already returns {"result": ...} on hits; mirror that here
            return {"result": raw or {}}
        # flight providers do their own normalization
        return raw


# ------------------------------ Providers ------------------------------
class OpenWeatherMapClient(ProviderClient):
    baseUrl = "https://api.openweathermap.org/data/2.5"
    providerName = "openweathermap"
    category = "weather"

    def fetch(self, icaoOrIata: str) -> Dict[str, Any]:
        user_input = (icaoOrIata or "")
        cache_key = sha256Stable(user_input.strip())

        def do_fetch():
            url, params = self.buildUrl(
                "/weather",
                {
                    "q": user_input.strip(),  # keep what the user typed
                    "appid": os.getenv("OPENWEATHERMAP_API_KEY"),
                    "units": os.getenv("WEATHER_UNITS", "metric"),
                    },
            )
            return self.safeRequest("GET", url, params=params)

        return self.getCachedOrFetch(cache_key, DEFAULT_TTLS["weather"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        obj, _ = AirportWeather.objects.select_for_update().get_or_create(
            # cacheKey is now a sha256 hash of the original input; icao/iata are not derivable from it.
            key = cacheKey,
            providerSource = self.providerName,
            defaults = {"conditionsJson": raw},
        )
        obj.conditionsJson = raw
        obj.save()


class AviationWeatherClient(ProviderClient):
    baseUrl = "https://aviationweather.gov/api"
    providerName = "aviationweather"
    category = "weather"

    def fetch(self, icao: str) -> Dict[str, Any]:
        key = icao.strip().upper()

        def do_fetch():
            url, params = self.buildUrl(
                "/data/metar",
                {"ids": key, "format": "json", "apikey": os.getenv("AVIATIONWEATHER_API_KEY")},
            )
            return self.safeRequest("GET", url, params=params)

        return self.getCachedOrFetch(key, DEFAULT_TTLS["weather"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        obj, _ = AirportWeather.objects.select_for_update().get_or_create(
            key=cacheKey,
            providerSource=self.providerName,
            defaults={"icao": cacheKey, "conditionsJson": raw},
        )
        obj.conditionsJson = raw
        obj.save()


class AviationStackClient(ProviderClient):
    baseUrl = "http://api.aviationstack.com/v1"
    providerName = "aviationstack"
    category = "flight"

    def fetch(self, **kwargs) -> Dict[str, Any]:
        qhash = sha256Stable(kwargs)

        def do_fetch():
            url, params = self.buildUrl("/flights", {**kwargs, "access_key": os.getenv("AVIATIONSTACK_API_KEY")})
            return self.safeRequest("GET", url, params=params)

        return self.getCachedOrFetch(qhash, DEFAULT_TTLS["flight"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        data = raw.get("data") or []
        first = data[0] if data else {}
        norm = {
            "flightNumber": (first.get("flight", {}) or {}).get("iata"),
            "airline": (first.get("airline", {}) or {}).get("name"),
            "depIata": (first.get("departure", {}) or {}).get("iata"),
            "arrIata": (first.get("arrival", {}) or {}).get("iata"),
            "status": first.get("flight_status"),
            "depTime": (first.get("departure", {}) or {}).get("scheduled"),
            "arrTime": (first.get("arrival", {}) or {}).get("scheduled"),
        }
        obj, _ = Flight.objects.select_for_update().get_or_create(
            queryHash=cacheKey, providerSource=self.providerName, defaults={**norm, "rawJson": raw}
        )
        for k, v in norm.items():
            setattr(obj, k, v)
        obj.rawJson = raw
        obj.save()

    def _normalizeForReturn(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        data = raw.get("data") or []
        first = data[0] if data else {}
        return {
            "flightNumber": (first.get("flight", {}) or {}).get("iata"),
            "airline": (first.get("airline", {}) or {}).get("name"),
            "depIata": (first.get("departure", {}) or {}).get("iata"),
            "arrIata": (first.get("arrival", {}) or {}).get("iata"),
            "status": first.get("flight_status"),
            "depTime": (first.get("departure", {}) or {}).get("scheduled"),
            "arrTime": (first.get("arrival", {}) or {}).get("scheduled"),
            "raw": raw,
        }


class OpenSkyClient(ProviderClient):
    baseUrl = "https://opensky-network.org/api"
    providerName = "opensky"
    category = "flight"

    def fetch(self, bbox: Tuple[float, float, float, float] | None = None, icao24: str | None = None, callsign: str | None = None) -> Dict[str, Any]:
        params = {}
        path = "/states/all"
        if bbox:
            params["lamin"], params["lomin"], params["lamax"], params["lomax"] = bbox
        if icao24:
            params["icao24"] = icao24
        if callsign:
            params["callsign"] = callsign
        qhash = sha256Stable(params or "all")

        def do_fetch():
            url, _ = self.buildUrl(path, params)
            user = os.getenv("OPENSKY_USERNAME"); pwd = os.getenv("OPENSKY_PASSWORD")
            auth = HTTPBasicAuth(user, pwd) if user and pwd else None
            return self.safeRequest("GET", url, params=params, auth=auth)

        return self.getCachedOrFetch(qhash, DEFAULT_TTLS["flight"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        states = raw.get("states") or []
        first = states[0] if states else []
        norm = {
            "flightNumber": (first[1].strip() if len(first) > 1 and first[1] else None),
            "airline": None,
            "depIata": None,
            "arrIata": None,
            "status": "airborne" if states else None,
            "depTime": None,
            "arrTime": None,
        }
        obj, _ = Flight.objects.select_for_update().get_or_create(
            queryHash=cacheKey, providerSource=self.providerName, defaults={**norm, "rawJson": raw}
        )
        for k, v in norm.items():
            setattr(obj, k, v)
        obj.rawJson = raw
        obj.save()

    def _normalizeForReturn(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        states = raw.get("states") or []
        first = states[0] if states else []
        return {
            "flightNumber": (first[1].strip() if len(first) > 1 and first[1] else None),
            "airline": None,
            "depIata": None,
            "arrIata": None,
            "status": "airborne" if states else None,
            "depTime": None,
            "arrTime": None,
            "raw": raw,
        }


class OpenStreetMapClient(ProviderClient):
    baseUrl = "https://nominatim.openstreetmap.org"
    providerName = "openstreetmap"
    category = "geo"

    def fetch(self, query: str) -> Dict[str, Any]:
        qhash = sha256Stable(query)

        def do_fetch():
            url, params = self.buildUrl(
                "/search",
                {"q": query, "format": "json", "limit": 3, "email": os.getenv("OPENSTREETMAP_EMAIL")},
            )
            headers = {
                "User-Agent": f"flight-app/1.0 ({os.getenv('OPENSTREETMAP_EMAIL') or 'contact@example.com'})",
            }
            return self.safeRequest("GET", url, params=params, headers=headers)

        return self.getCachedOrFetch(qhash, DEFAULT_TTLS["geo"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        obj, _ = MapsGeo.objects.select_for_update().get_or_create(
            queryHash=cacheKey, providerSource=self.providerName, defaults={"resultJson": raw}
        )
        obj.resultJson = raw
        obj.save()


# ------------------------------
# Thin wrappers (kept compatible)
# ------------------------------

def fetchOpenWeatherMap(icaoOrIata: str) -> dict:
    return OpenWeatherMapClient().fetch(icaoOrIata)


def getOpenWeatherMapFromDb(icaoOrIata: str) -> dict:
    cand = (icaoOrIata or "").strip()
    # If caller passed a 64-char hex, treat as hash directly
    is_hash = len(cand) == 64 and all(c in "0123456789abcdefABCDEF" for c in cand)
    if is_hash:
        row = AirportWeather.objects.filter(key=cand, providerSource="openweathermap").first()
        return {"weather": row.conditionsJson} if row else {}

    # Otherwise, try the uppercased raw key and also the sha256 of that key
    raw_key = cand.upper()
    row = AirportWeather.objects.filter(
        key__in=[raw_key, sha256Stable(raw_key)],
        providerSource="openweathermap",
    ).first()
    return {"weather": row.conditionsJson} if row else {}


def fetchAviationWeather(icao: str, session: requests.Session | None = None):
    # Use our client to benefit from cache/budgets; keep the tests-friendly signature intact.
    return AviationWeatherClient().fetch(icao)


def getAviationWeatherFromDb(icao: str) -> dict:
    key = icao.strip().upper()
    row = AirportWeather.objects.filter(key=key, providerSource="aviationweather").first()
    return {"weather": row.conditionsJson} if row else {}


def fetchAviationStackFlight(flightNumber=None, airline=None, depIata=None, arrIata=None, onlyAirborne=None, onlyDelayed=None) -> dict:
    params: Dict[str, Any] = {}
    if flightNumber:
        params["flight_iata"] = flightNumber
    if airline:
        params["airline_name"] = airline
    if depIata:
        params["dep_iata"] = depIata
    if arrIata:
        params["arr_iata"] = arrIata
    if onlyAirborne:
        params["status"] = "active"
    if onlyDelayed:
        params["delayed"] = "true"
    return AviationStackClient().fetch(**params)


def getAviationStackFromDb(queryHash: str) -> dict:
    row = Flight.objects.filter(queryHash=queryHash, providerSource="aviationstack").first()
    if not row:
        return {}
    return {
        "flightNumber": row.flightNumber,
        "airline": row.airline,
        "depIata": row.depIata,
        "arrIata": row.arrIata,
        "status": row.status,
        "depTime": row.depTime,
        "arrTime": row.arrTime,
        "raw": row.rawJson,
    }


def fetchOpenSkyFlights(bbox=None, icao24=None, callsign=None) -> dict:
    return OpenSkyClient().fetch(bbox=bbox, icao24=icao24, callsign=callsign)


def getOpenSkyFromDb(queryHash: str) -> dict:
    row = Flight.objects.filter(queryHash=queryHash, providerSource="opensky").first()
    if not row:
        return {}
    return {
        "flightNumber": row.flightNumber,
        "airline": row.airline,
        "depIata": row.depIata,
        "arrIata": row.arrIata,
        "status": row.status,
        "depTime": row.depTime,
        "arrTime": row.arrTime,
        "raw": row.rawJson,
    }


def callAi(jsonPrompt: dict) -> dict:
    return {"provider": "local-sandbox", "received": jsonPrompt, "result": {"ok": True}}

# =============================
# \n# PACK: Conservative API + Usage Ledger + Admin Readout
# (Drop-in updates & new files)
# =============================

# --- File: APICalls_conservative.py (updated) ---


logger = logging.getLogger("apiCalls")
logger.setLevel(logging.INFO)

# ------------------------------
# Configuration (ENV-configurable)
# ------------------------------
# TTLs (freshness windows) — env overrides with sane conservative defaults
DEFAULT_TTLS = {
    "weather": int(os.getenv("WEATHER_TTL_SECS", 1800)),  # 30 min
    "flight": int(os.getenv("FLIGHT_TTL_SECS", 90)),     # 90 sec
    "geo": int(os.getenv("GEO_TTL_SECS", 86400)),        # 24 h
}

# Serve-stale windows when provider errors or daily budget exhausted
MAX_STALE = {
    "weather": int(os.getenv("WEATHER_MAX_STALE_SECS", 6 * 3600)),
    "flight": int(os.getenv("FLIGHT_MAX_STALE_SECS", 10 * 60)),
    "geo": int(os.getenv("GEO_MAX_STALE_SECS", 7 * 86400)),
}

# Daily budgets per provider (env with defaults)
DAILY_BUDGETS = {
    "openweathermap": int(os.getenv("BUDGET_OPENWEATHERMAP_PER_DAY", 900)),
    "aviationweather": int(os.getenv("BUDGET_AVIATIONWEATHER_PER_DAY", 2000)),
    "aviationstack": int(os.getenv("BUDGET_AVIATIONSTACK_PER_DAY", 1000)),
    "opensky": int(os.getenv("BUDGET_OPENSPY_PER_DAY", 380)) if os.getenv("BUDGET_OPENSPY_PER_DAY") else int(os.getenv("BUDGET_OPENSKY_PER_DAY", 380)),
}

class SimpleRateLimiter:
    def __init__(self, rate_per_sec: float = 1.0, capacity: int = 1):
        self.rate = rate_per_sec
        self.capacity = capacity
        self.tokens = capacity
        self.last = time.monotonic()

    def acquire(self, tokens: float = 1.0):
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        sleep_time = (tokens - self.tokens) / self.rate
        time.sleep(max(0, sleep_time))
        self.tokens = 0
        return True

limiters = {
    "openweathermap": SimpleRateLimiter(rate_per_sec=2/1.0, capacity=2),
    "aviationweather": SimpleRateLimiter(rate_per_sec=0.8, capacity=1),
    "aviationstack": SimpleRateLimiter(rate_per_sec=1/61.0, capacity=1),
    "opensky": SimpleRateLimiter(rate_per_sec=0.2, capacity=1),
    "openstreetmap": SimpleRateLimiter(rate_per_sec=0.5, capacity=1),
}

# ------------------------------
# Daily Usage Ledger (ORM-backed)
# ------------------------------

def _today_key() -> str:
    return dj_tz.now().astimezone(_tz.utc).strftime("%Y%m%d")


def get_usage(provider: str) -> int:
    row = ApiUsage.objects.filter(provider=provider, yyyymmdd=_today_key()).first()
    return int(row.count) if row else 0


def add_usage(provider: str, n: int = 1):
    obj, created = ApiUsage.objects.get_or_create(provider=provider, yyyymmdd=_today_key(), defaults={"count": 0})
    # race-safe increment
    ApiUsage.objects.filter(pk=obj.pk).update(count=F("count") + n)


def under_budget(provider: str) -> bool:
    budget = DAILY_BUDGETS.get(provider)
    if not budget:
        return True
    return get_usage(provider) < budget

# ------------------------------
# Helpers
# ------------------------------

def sha256Stable(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":")) if not isinstance(obj, str) else obj
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class ProviderResponse:
    data: Dict[str, Any]
    provider: str
    cache: str  # "hit" | "miss" | "stale"


class OpenWeatherMapClient(ProviderClient):
    baseUrl = "https://api.openweathermap.org/data/2.5"
    providerName = "openweathermap"
    category = "weather"

    def fetch(self, icaoOrIata: str) -> Dict[str, Any]:
        key = icaoOrIata.strip().upper()
        def do_fetch():
            url, params = self.buildUrl(
                "/weather",
                {"q": key, "appid": os.getenv("OPENWEATHERMAP_API_KEY"), "units": os.getenv("WEATHER_UNITS", "metric")},
            )
            return self.safeRequest("GET", url, params=params)
        return self.getCachedOrFetch(key, DEFAULT_TTLS["weather"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        obj, _ = AirportWeather.objects.select_for_update().get_or_create(
            key=cacheKey,
            providerSource=self.providerName,
            defaults={
                "icao": cacheKey if len(cacheKey) == 4 else None,
                "iata": cacheKey if len(cacheKey) == 3 else None,
                "conditionsJson": raw,
            },
        )
        obj.conditionsJson = raw
        obj.save()


class AviationWeatherClient(ProviderClient):
    baseUrl = "https://aviationweather.gov/api"
    providerName = "aviationweather"
    category = "weather"

    def fetch(self, icao: str) -> Dict[str, Any]:
        key = icao.strip().upper()
        def do_fetch():
            url, params = self.buildUrl(
                "/data/metar",
                {"ids": key, "format": "json", "apikey": os.getenv("AVIATIONWEATHER_API_KEY")},
            )
            return self.safeRequest("GET", url, params=params)
        return self.getCachedOrFetch(key, DEFAULT_TTLS["weather"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        obj, _ = AirportWeather.objects.select_for_update().get_or_create(
            key=cacheKey,
            providerSource=self.providerName,
            defaults={"icao": cacheKey, "conditionsJson": raw},
        )
        obj.conditionsJson = raw
        obj.save()


class AviationStackClient(ProviderClient):
    baseUrl = "http://api.aviationstack.com/v1"
    providerName = "aviationstack"
    category = "flight"

    def fetch(self, **kwargs) -> Dict[str, Any]:
        qhash = sha256Stable(kwargs)
        def do_fetch():
            url, params = self.buildUrl("/flights", {**kwargs, "access_key": os.getenv("AVIATIONSTACK_API_KEY")})
            return self.safeRequest("GET", url, params=params)
        return self.getCachedOrFetch(qhash, DEFAULT_TTLS["flight"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        data = raw.get("data") or []
        first = data[0] if data else {}
        norm = {
            "flightNumber": (first.get("flight", {}) or {}).get("iata"),
            "airline": (first.get("airline", {}) or {}).get("name"),
            "depIata": (first.get("departure", {}) or {}).get("iata"),
            "arrIata": (first.get("arrival", {}) or {}).get("iata"),
            "status": first.get("flight_status"),
            "depTime": (first.get("departure", {}) or {}).get("scheduled"),
            "arrTime": (first.get("arrival", {}) or {}).get("scheduled"),
        }
        obj, _ = Flight.objects.select_for_update().get_or_create(
            queryHash=cacheKey, providerSource=self.providerName, defaults={**norm, "rawJson": raw}
        )
        for k, v in norm.items():
            setattr(obj, k, v)
        obj.rawJson = raw
        obj.save()

    def _normalizeForReturn(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        data = raw.get("data") or []
        first = data[0] if data else {}
        return {
            "flightNumber": (first.get("flight", {}) or {}).get("iata"),
            "airline": (first.get("airline", {}) or {}).get("name"),
            "depIata": (first.get("departure", {}) or {}).get("iata"),
            "arrIata": (first.get("arrival", {}) or {}).get("iata"),
            "status": first.get("flight_status"),
            "depTime": (first.get("departure", {}) or {}).get("scheduled"),
            "arrTime": (first.get("arrival", {}) or {}).get("scheduled"),
            "raw": raw,
        }


class OpenSkyClient(ProviderClient):
    baseUrl = "https://opensky-network.org/api"
    providerName = "opensky"
    category = "flight"

    def fetch(self, bbox: Tuple[float, float, float, float] | None = None, icao24: str | None = None, callsign: str | None = None) -> Dict[str, Any]:
        params = {}
        path = "/states/all"
        if bbox:
            params["lamin"], params["lomin"], params["lamax"], params["lomax"] = bbox
        if icao24:
            params["icao24"] = icao24
        if callsign:
            params["callsign"] = callsign
        qhash = sha256Stable(params or "all")
        def do_fetch():
            url, _ = self.buildUrl(path, params)
            user = os.getenv("OPENSKY_USERNAME"); pwd = os.getenv("OPENSKY_PASSWORD")
            auth = HTTPBasicAuth(user, pwd) if user and pwd else None
            return self.safeRequest("GET", url, params=params, auth=auth)
        return self.getCachedOrFetch(qhash, DEFAULT_TTLS["flight"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        states = raw.get("states") or []
        first = states[0] if states else []
        norm = {
            "flightNumber": (first[1].strip() if len(first) > 1 and first[1] else None),
            "airline": None,
            "depIata": None,
            "arrIata": None,
            "status": "airborne" if states else None,
            "depTime": None,
            "arrTime": None,
        }
        obj, _ = Flight.objects.select_for_update().get_or_create(
            queryHash=cacheKey, providerSource=self.providerName, defaults={**norm, "rawJson": raw}
        )
        for k, v in norm.items():
            setattr(obj, k, v)
        obj.rawJson = raw
        obj.save()

    def _normalizeForReturn(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        states = raw.get("states") or []
        first = states[0] if states else []
        return {
            "flightNumber": (first[1].strip() if len(first) > 1 and first[1] else None),
            "airline": None,
            "depIata": None,
            "arrIata": None,
            "status": "airborne" if states else None,
            "depTime": None,
            "arrTime": None,
            "raw": raw,
        }


class OpenStreetMapClient(ProviderClient):
    baseUrl = "https://nominatim.openstreetmap.org"
    providerName = "openstreetmap"
    category = "geo"

    def fetch(self, query: str) -> Dict[str, Any]:
        qhash = sha256Stable(query)
        def do_fetch():
            url, params = self.buildUrl(
                "/search",
                {"q": query, "format": "json", "limit": 3, "email": os.getenv("OPENSTREETMAP_EMAIL")},
            )
            headers = {
                "User-Agent": f"flight-app/1.0 ({os.getenv('OPENSTREETMAP_EMAIL') or 'contact@example.com'})",
            }
            return self.safeRequest("GET", url, params=params, headers=headers)
        return self.getCachedOrFetch(qhash, DEFAULT_TTLS["geo"], do_fetch).data

    @transaction.atomic
    def _upsert(self, cacheKey: str, raw: Dict[str, Any]):
        obj, _ = MapsGeo.objects.select_for_update().get_or_create(
            queryHash=cacheKey, providerSource=self.providerName, defaults={"resultJson": raw}
        )
        obj.resultJson = raw
        obj.save()


# Thin wrappers (backwards-compatible)

def fetchOpenWeatherMap(icaoOrIata: str) -> dict:
    return OpenWeatherMapClient().fetch(icaoOrIata)

def getOpenWeatherMapFromDb(icaoOrIata: str) -> dict:
    cand = icaoOrIata.strip()
    is_hash = (len(cand) == 64) and all(c in "0123456789abcdefABCDEF" for c in cand)

    if is_hash:
        keys = [cand]  # use the hash as-is (don't upper-case)
    else:
        raw_key = cand.upper()
        keys = [raw_key, sha256Stable(raw_key)]

    row = AirportWeather.objects.filter(key__in=keys, providerSource="openweathermap").first()
    return {"weather": row.conditionsJson} if row else {}



def fetchAviationWeather(icao: str, session: requests.Session | None = None):
    return AviationWeatherClient().fetch(icao)


def getAviationWeatherFromDb(icao: str) -> dict:
    key = icao.strip().upper()
    row = AirportWeather.objects.filter(key=key, providerSource="aviationweather").first()
    return {"weather": row.conditionsJson} if row else {}


def fetchAviationStackFlight(flightNumber=None, airline=None, depIata=None, arrIata=None, onlyAirborne=None, onlyDelayed=None) -> dict:
    params: Dict[str, Any] = {}
    if flightNumber:
        params["flight_iata"] = flightNumber
    if airline:
        params["airline_name"] = airline
    if depIata:
        params["dep_iata"] = depIata
    if arrIata:
        params["arr_iata"] = arrIata
    if onlyAirborne:
        params["status"] = "active"
    if onlyDelayed:
        params["delayed"] = "true"
    return AviationStackClient().fetch(**params)


def getAviationStackFromDb(queryHash: str) -> dict:
    row = Flight.objects.filter(queryHash=queryHash, providerSource="aviationstack").first()
    if not row:
        return {}
    return {
        "flightNumber": row.flightNumber,
        "airline": row.airline,
        "depIata": row.depIata,
        "arrIata": row.arrIata,
        "status": row.status,
        "depTime": row.depTime,
        "arrTime": row.arrTime,
        "raw": row.rawJson,
    }


def fetchOpenSkyFlights(bbox=None, icao24=None, callsign=None) -> dict:
    return OpenSkyClient().fetch(bbox=bbox, icao24=icao24, callsign=callsign)


def getOpenSkyFromDb(queryHash: str) -> dict:
    row = Flight.objects.filter(queryHash=queryHash, providerSource="opensky").first()
    if not row:
        return {}
    return {
        "flightNumber": row.flightNumber,
        "airline": row.airline,
        "depIata": row.depIata,
        "arrIata": row.arrIata,
        "status": row.status,
        "depTime": row.depTime,
        "arrTime": row.arrTime,
        "raw": row.rawJson,
    }


def callAi(jsonPrompt: dict) -> dict:
    return {"provider": "local-sandbox", "received": jsonPrompt, "result": {"ok": True}}


# --- File: models.py (add this model) ---
from django.db import models

# class ApiUsage(models.Model):
#     provider = models.CharField(max_length=40, db_index=True)
#     yyyymmdd = models.CharField(max_length=8, db_index=True)
#     count = models.IntegerField(default=0)
#
#     class Meta:
#         unique_together = ("provider", "yyyymmdd")
#         indexes = [models.Index(fields=["provider", "yyyymmdd"]) ]
#
#     def __str__(self):
#         return f"{self.provider} {self.yyyymmdd}: {self.count}"


# --- File: migrations/0002_apiusage.py ---
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("YOUR_APP_LABEL", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiUsage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(db_index=True, max_length=40)),
                ("yyyymmdd", models.CharField(db_index=True, max_length=8)),
                ("count", models.IntegerField(default=0)),
            ],
            options={
                "unique_together": {("provider", "yyyymmdd")},
                "indexes": [models.Index(fields=["provider", "yyyymmdd"], name="ix_apiusage_provider_day")],
            },
        ),
    ]


# --- File: admin.py (register model + quick link) ---
from django.contrib import admin
from .models import ApiUsage

@admin.register(ApiUsage)
class ApiUsageAdmin(admin.ModelAdmin):
    list_display = ("provider", "yyyymmdd", "count")
    list_filter = ("provider", "yyyymmdd")
    search_fields = ("provider",)
    ordering = ("-yyyymmdd", "provider")


# --- File: views.py (admin/readout endpoint) ---


def _budgets_from_env():
    return {
        "openweathermap": int(os.getenv("BUDGET_OPENWEATHERMAP_PER_DAY", 900)),
        "aviationweather": int(os.getenv("BUDGET_AVIATIONWEATHER_PER_DAY", 2000)),
        "aviationstack": int(os.getenv("BUDGET_AVIATIONSTACK_PER_DAY", 1000)),
        "opensky": int(os.getenv("BUDGET_OPENSKY_PER_DAY", int(os.getenv("BUDGET_OPENSPY_PER_DAY", 380)))),
    }

@staff_member_required
def api_usage_readout(request):
    today = timezone.now().astimezone(_tz.utc).strftime("%Y%m%d")
    budgets = _budgets_from_env()
    rows = ApiUsage.objects.filter(yyyymmdd=today).values("provider").annotate(total=Sum("count"))
    used = {r["provider"]: r["total"] for r in rows}
    out = []
    for provider, budget in budgets.items():
        u = int(used.get(provider, 0))
        remaining = max(0, budget - u)
        pct = (u / budget * 100.0) if budget else None
        out.append({
            "provider": provider,
            "used_today": u,
            "budget_today": budget,
            "remaining_today": remaining,
            "used_pct": round(pct, 1) if pct is not None else None,
        })
    return JsonResponse({"date": today, "providers": out})


# --- File: urls.py (wire the readout) ---


urlpatterns = [
    # ... your other urls
    path("admin/api-usage/", api_usage_readout, name="api_usage_readout"),
]




# class AirLabsClient(AviationStackClient):
#     baseUrl = "https://airlabs.co/api/v9"; providerName="airlabs"
#     def fetch(self, **kwargs) -> Dict[str, Any]:
#         qhash = sha256Stable(kwargs)
#         def do_fetch():
#             url, params = self.buildUrl("/flights", {**kwargs, "api_key": os.getenv("AIRLABS_API_KEY")})
#             return self.safeRequest("GET", url, params=params)
#         return self.getCachedOrFetch(qhash, DEFAULT_TTLS["flight"], do_fetch).data

# class MapboxClient(OpenStreetMapClient):
#     baseUrl = "https://api.mapbox.com/geocoding/v5/mapbox.places"; providerName="mapbox"
#     def fetch(self, query: str) -> Dict[str, Any]:
#         qhash = sha256Stable(query)
#         def do_fetch():
#             token = os.getenv("MAPBOX_API_KEY"); import requests as _rq
#             url = f"{self.baseUrl}/{_rq.utils.quote(query)}.json"; params = {"access_token": token, "limit": 3}
#             return self.safeRequest("GET", url, params=params)
#         return self.getCachedOrFetch(qhash, DEFAULT_TTLS["geo"], do_fetch).data

# Thin wrappers

# def fetchAirLabsFlight(**kwargs) -> dict: return AirLabsClient().fetch(**kwargs)
# def getAirLabsFromDb(queryHash: str) -> dict:
#     row = Flight.objects.filter(queryHash=queryHash, providerSource="airlabs").first()
#     if not row: return {}
#     return {"flightNumber": row.flightNumber, "airline": row.airline, "depIata": row.depIata, "arrIata": row.arrIata, "status": row.status, "depTime": row.depTime, "arrTime": row.arrTime, "raw": row.rawJson}



# def fetchOpenStreetMap(query: str) -> dict: return OpenStreetMapClient().fetch(query)
# def getOpenStreetMapFromDb(queryHash: str) -> dict:
#     row = MapsGeo.objects.filter(queryHash=queryHash, providerSource="openstreetmap").first()
#     return {"result": row.resultJson} if row else {}

# def fetchMapboxGeocode(query: str) -> dict: return MapboxClient().fetch(query)
# def getMapboxFromDb(queryHash: str) -> dict:
#     row = MapsGeo.objects.filter(queryHash=queryHash, providerSource="mapbox").first()
#     return {"result": row.resultJson} if row else {}

def callAi(jsonPrompt: dict) -> dict:
    return {"provider": "local-sandbox", "received": jsonPrompt, "result": {"ok": True}}
