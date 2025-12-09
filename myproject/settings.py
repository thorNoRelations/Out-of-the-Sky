"""
Django settings for myproject project.
All configuration from environment variables.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file (if it exists)
# This loads the .env file in the project root
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded .env file from {env_path}")
else:
    # On Render, environment variables are set directly, so this is fine
    print("ℹ️  No .env file found - using system environment variables")

# Detect if we're running tests
TESTING = (
    "test" in sys.argv
    or "pytest" in sys.modules
    or os.environ.get("PYTEST_CURRENT_TEST")
)

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-key-change-in-production"
)

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    'out-of-the-sky.onrender.com',
    'localhost',
    '127.0.0.1',
    'out-of-the-sky.xyz',
    'www.out-of-the-sky.xyz',
]

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'home',
    'search',
    'backend',
    'accounts',
]

LOGIN_REDIRECT_URL = 'profile'
LOGOUT_REDIRECT_URL = 'home:index'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'myproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'myproject.wsgi.application'

# =============================================================================
# DATABASE
# =============================================================================


data_dir = Path(os.environ.get("RENDER_DATA_DIR", BASE_DIR))
db_path = data_dir / "db.sqlite3"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": db_path,
    }
}

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES
# =============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'home' / 'static',
    BASE_DIR / 'search' / 'static',
]

if TESTING:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# API CONFIGURATION - ALL FROM ENVIRONMENT VARIABLES
# =============================================================================

# OpenWeather API Configuration
# The .env file has quotes around the key - strip them
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "").strip('"\'')

# Validate that we have the key (unless testing)
if not TESTING and not OPENWEATHER_API_KEY:
    print("=" * 80)
    print("⚠️  WARNING: OPENWEATHER_API_KEY is not set!")
    print("=" * 80)
    print("Available environment variables with 'WEATHER' or 'OPEN':")
    for key in os.environ.keys():
        if 'WEATHER' in key.upper() or 'OPEN' in key.upper():
            value = os.environ[key]
            # Show first 8 and last 4 characters for debugging
            if len(value) > 12:
                print(f"  {key}: {value[:8]}...{value[-4:]}")
            else:
                print(f"  {key}: (too short)")
    print("=" * 80)

# Weather API Settings
WEATHER_UNITS = os.environ.get("WEATHER_UNITS", "imperial").strip('"\'')
WEATHER_CACHE_TTL_SECONDS = int(os.environ.get("WEATHER_CACHE_TTL_SECONDS", "300"))

# OpenAI API Configuration
OPENAI_API_KEY = os.environ.get("OPEN_AI_KEY", "").strip('"\'')

# API Usage Budgets
BUDGET_OPENWEATHERMAP_PER_DAY = int(
    os.environ.get("OPENWEATHER_DAILY_QUOTA",
                   os.environ.get("BUDGET_OPENWEATHERMAP_PER_DAY", "2000"))
)
BUDGET_AVIATIONWEATHER_PER_DAY = int(
    os.environ.get("BUDGET_AVIATIONWEATHER_PER_DAY", "2000")
)
BUDGET_AVIATIONSTACK_PER_DAY = int(
    os.environ.get("BUDGET_AVIATIONSTACK_PER_DAY", "1000")
)
BUDGET_OPENSKY_PER_DAY = int(
    os.environ.get("BUDGET_OPENSKY_PER_DAY", "380")
)

# =============================================================================
# CONFIGURATION SUMMARY (for debugging)
# =============================================================================

if DEBUG and not TESTING:
    print("\n" + "=" * 80)
    print("🔧 CONFIGURATION SUMMARY")
    print("=" * 80)
    print(f"DEBUG: {DEBUG}")
    print(f"OPENWEATHER_API_KEY configured: {'✓' if OPENWEATHER_API_KEY else '✗'}")
    if OPENWEATHER_API_KEY:
        print(f"  Key length: {len(OPENWEATHER_API_KEY)} characters")
        print(f"  Key preview: {OPENWEATHER_API_KEY[:8]}...{OPENWEATHER_API_KEY[-4:]}")
    print(f"WEATHER_UNITS: {WEATHER_UNITS}")
    print(f"WEATHER_CACHE_TTL: {WEATHER_CACHE_TTL_SECONDS}s")
    print(f"OPENAI_API_KEY configured: {'✓' if OPENAI_API_KEY else '✗'}")
    print(f"Daily API Budget: {BUDGET_OPENWEATHERMAP_PER_DAY} calls")
    print("=" * 80 + "\n")
