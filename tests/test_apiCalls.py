import json
import pytest
from unittest.mock import patch
from backend.APICalls import OpenWeatherClient
from backend.models import APIRequestLog, AirportWeather

pytestmark = pytest.mark.django_db


class DummyResp:
    def __init__(self, status_code=200, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)
        self.headers = headers or {"Content-Length": str(len(self.text)), "Content-Type": "application/json"}

    def json(self):
        return self._payload


def test_missing_api_key_raises(settings, monkeypatch):
    # Ensure no key in settings or env
    if hasattr(settings, "OPENWEATHER_API_KEY"):
        delattr(settings, "OPENWEATHER_API_KEY")
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    with pytest.raises(RuntimeError) as e:
        OpenWeatherClient()
    assert "OPENWEATHER_API_KEY" in str(e.value)


def test_success_logs_one_call(monkeypatch, settings):
    settings.OPENWEATHER_API_KEY = "dummy"
    settings.WEATHER_UNITS = "metric"

    payload = {
        "name": "Denver",
        "sys": {"country": "US"},
        "main": {"temp": 18.5},
        "weather": [{"description": "clear sky"}]
    }

    def fake_get(url, params=None, timeout=15):
        return DummyResp(200, payload)

    with patch("backend.APICalls.requests.get", new=fake_get):
        client = OpenWeatherClient()
        data = client.fetch_city("Denver,US")
        assert data["main"]["temp"] == 18.5

    # Exactly one log row
    logs = list(APIRequestLog.objects.all())
    assert len(logs) == 1
    log = logs[0]
    assert log.provider == "openweathermap"
    assert log.endpoint == "/data/2.5/weather"
    assert log.status_code == 200
    assert log.latency_ms is not None


def test_error_is_logged_and_raised(monkeypatch, settings):
    settings.OPENWEATHER_API_KEY = "dummy"

    def fake_get(url, params=None, timeout=15):
        return DummyResp(401, {"cod": 401, "message": "Invalid API key"})

    with patch("backend.APICalls.requests.get", new=fake_get):
        client = OpenWeatherClient()
        with pytest.raises(RuntimeError) as e:
            client.fetch_city("Nowhere,ZZ")
        assert "Invalid API key" in str(e.value)

    logs = list(APIRequestLog.objects.all())
    assert len(logs) == 1
    assert logs[0].status_code == 401
    assert "Invalid API key" in (logs[0].error_message or "")


def test_success_logs_and_saves_weather(monkeypatch, settings):
    settings.OPENWEATHER_API_KEY = "dummy"
    settings.WEATHER_UNITS = "metric"

    payload = {
        "name": "Denver",
        "sys": {"country": "US"},
        "main": {"temp": 18.5},
        "weather": [{"description": "clear sky"}]
    }

    def fake_get(url, params=None, timeout=15):
        return DummyResp(200, payload)

    with patch("backend.APICalls.requests.get", new=fake_get):
        client = OpenWeatherClient()
        data = client.fetch_city("Denver,US")
        assert data["main"]["temp"] == 18.5

    # Exactly one log row
    logs = list(APIRequestLog.objects.all())
    assert len(logs) == 1

    # NEW: the latest payload is saved for weather map usage
    aw = AirportWeather.objects.get(providerSource="openweathermap", key="denver,us")
    assert aw.conditionsJson["main"]["temp"] == 18.5
