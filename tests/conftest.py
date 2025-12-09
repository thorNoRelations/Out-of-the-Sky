
import os
import pytest

# Use test env
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
os.environ.setdefault("DATABASE_URL", "sqlite:///./db.sqlite3")
os.environ.setdefault("OPENWEATHERMAP_API_KEY", "owm_test")
os.environ.setdefault("AVIATIONWEATHER_API_KEY", "avwx_test")
os.environ.setdefault("AVIATIONSTACK_API_KEY", "astack_test")
os.environ.setdefault("AIRLABS_API_KEY", "airlabs_test")
os.environ.setdefault("MAPBOX_API_KEY", "mapbox_test")
os.environ.setdefault("OPENSTREETMAP_EMAIL", "tester@example.com")


@pytest.fixture(autouse=True)
def _setup_env(settings):
    # ensure backend app is in INSTALLED_APPS for tests
    if "backend" not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS.append("backend")
