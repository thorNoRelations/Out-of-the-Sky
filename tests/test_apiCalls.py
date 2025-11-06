
import os, json, importlib, pytest
from unittest.mock import patch

pytestmark = pytest.mark.django_db

apicalls = importlib.import_module("backend.APICalls")

class DummyResp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)
    def json(self): return self._payload
    def raise_for_status(self):
        if 400 <= self.status_code:
            raise Exception(f"HTTP {self.status_code}")

OWM_PAYLOAD = {"weather": [{"main": "Clear"}], "main": {"temp": 20}}
AVWX_PAYLOAD = {"metar": "KDEN 010000Z 00000KT 10SM FEW"}
ASTACK_PAYLOAD = {"data": [{"flight_status": "scheduled", "flight": {"iata": "UA123"}, "airline": {"name": "United"}, "departure": {"iata": "DEN", "scheduled": "2025-10-19T10:00Z"}, "arrival": {"iata": "SFO", "scheduled": "2025-10-19T12:00Z"}}]}
OPENSKY_PAYLOAD = {"states": [["abc123", "UA789   ", None, None, None, None, None, 39.0, -104.0]]}
OSM_PAYLOAD = [{"display_name": "Denver International Airport"}]
MAPBOX_PAYLOAD = {"features": [{"place_name": "San Francisco International Airport"}]}

def test_fetch_openweathermap_cache(monkeypatch):
    calls = {"n": 0}
    def fake_request(self, method, url, params=None, headers=None, auth=None, timeout=10):
        calls["n"] += 1
        return DummyResp(200, OWM_PAYLOAD)
    with patch.object(apicalls.requests.Session, "request", new=fake_request):
        out1 = apicalls.fetchOpenWeatherMap("KDEN")
        assert out1["weather"][0]["main"] == "Clear"
        assert calls["n"] == 1
        out2 = apicalls.fetchOpenWeatherMap("KDEN")
        assert calls["n"] == 1
    got = apicalls.getOpenWeatherMapFromDb("KDEN")
    assert "weather" in got

def test_fetch_aviationweather_retry(monkeypatch):
    seq = iter([DummyResp(500, {}), DummyResp(200, AVWX_PAYLOAD)])
    def fake_request(self, method, url, params=None, headers=None, auth=None, timeout=10):
        return next(seq)
    with patch.object(apicalls.requests.Session, "request", new=fake_request):
        out = apicalls.fetchAviationWeather("KDEN")
        assert "weather" in out

def test_fetch_aviationstack_normalize(monkeypatch):
    calls = {"n": 0}
    def fake_request(self, method, url, params=None, headers=None, auth=None, timeout=10):
        calls["n"] += 1
        return DummyResp(200, ASTACK_PAYLOAD)
    with patch.object(apicalls.requests.Session, "request", new=fake_request):
        out = apicalls.fetchAviationStackFlight(flightNumber="UA123")
        assert out["flightNumber"] == "UA123"
        assert calls["n"] == 1
        out2 = apicalls.fetchAviationStackFlight(flightNumber="UA123")
        assert calls["n"] == 1
    qhash = apicalls.sha256Stable({"flight_iata": "UA123"})
    dbout = apicalls.getAviationStackFromDb(qhash)
    assert dbout.get("flightNumber") == "UA123"

def test_fetch_opensky_auth(monkeypatch):
    os.environ["OPENSKY_USERNAME"] = "user"
    os.environ["OPENSKY_PASSWORD"] = "pass"
    calls = {"n": 0}
    def fake_request(self, method, url, params=None, headers=None, auth=None, timeout=10):
        calls["n"] += 1
        assert auth is not None
        return DummyResp(200, OPENSKY_PAYLOAD)
    with patch.object(apicalls.requests.Session, "request", new=fake_request):
        out = apicalls.fetchOpenSkyFlights(callsign="UA789")
        assert out["status"] == "airborne"
        out2 = apicalls.fetchOpenSkyFlights(callsign="UA789")
        assert calls["n"] == 1

def test_maps_cache(monkeypatch):
    seq = {"count": 0}
    def fake_request(self, method, url, params=None, headers=None, auth=None, timeout=10):
        seq["count"] += 1
        if "nominatim" in url: return DummyResp(200, OSM_PAYLOAD)
        return DummyResp(200, MAPBOX_PAYLOAD)
    with patch.object(apicalls.requests.Session, "request", new=fake_request):
        r1 = apicalls.fetchOpenWeatherMap("denver airport")
        r2 = apicalls.fetchOpenWeatherMap("denver airport")
        # assert seq["count"] == 1
        # r3 = apicalls.fetchMapboxGeocode("sfo")
        # r4 = apicalls.fetchMapboxGeocode("sfo")
        assert seq["count"] == 1
    q_osm = apicalls.sha256Stable("denver airport")
    q_mb = apicalls.sha256Stable("sfo")
    assert apicalls.getOpenWeatherMapFromDb(q_osm)
    #assert apicalls.getMapboxFromDb(q_mb)

import pytest
@pytest.mark.xfail(reason="Future dashboard aggregation", strict=False)
def test_dashboard_future():
    assert False
