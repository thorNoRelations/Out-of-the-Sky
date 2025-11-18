"""
Django settings for myproject project.
No .env file required - all settings configured directly here.
"""

import os
import sys
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Detect if we're running tests (both Django and pytest styles)
TESTING = (
    "test" in sys.argv
    or "pytest" in sys.modules
    or os.environ.get("PYTEST_CURRENT_TEST")
)

# SECURITY WARNING: keep the secret key used in production secret!
# For development, you can use this key. For production (Render), set as environment variable.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", 
    "django-insecure-dev-only-key-8x7f@2k9#m4p&q1w*3e$5r^6t+8y(0u)9i-0o=p[l]"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = [
    'out-of-the-sky.onrender.com',
    'localhost',
    '127.0.0.1',
]


# Application definition

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
]

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


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
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


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'home' / 'static',
    BASE_DIR / 'search' / 'static',
]

# Use different storage backends for testing vs production
if TESTING:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# API CONFIGURATION - Environment Variables
# =============================================================================

# OpenWeather API Configuration
# CRITICAL: Try multiple possible environment variable names
OPENWEATHER_API_KEY = (
    os.environ.get("OPENWEATHER_API_KEY") or 
    os.environ.get("OPENWEATHERMAP_API_KEY") or
    os.getenv("OPENWEATHER_API_KEY") or
    os.getenv("OPENWEATHERMAP_API_KEY") or
    ""
)

# Debug: Print to logs (remove after testing)
print(f"🔑 OPENWEATHER_API_KEY configured: {bool(OPENWEATHER_API_KEY)}")
print(f"🔑 Key length: {len(OPENWEATHER_API_KEY) if OPENWEATHER_API_KEY else 0}")

# Weather units: 'imperial' (Fahrenheit), 'metric' (Celsius), or 'standard' (Kelvin)
WEATHER_UNITS = os.environ.get("WEATHER_UNITS", "imperial")

# OpenAI API Configuration (optional - for future AI enhancements)
OPENAI_API_KEY = os.environ.get("OPEN_AI_KEY", "")

# API Usage Budgets (optional - for tracking API call limits)
BUDGET_OPENWEATHERMAP_PER_DAY = int(os.environ.get("BUDGET_OPENWEATHERMAP_PER_DAY", "900"))
BUDGET_AVIATIONWEATHER_PER_DAY = int(os.environ.get("BUDGET_AVIATIONWEATHER_PER_DAY", "2000"))
BUDGET_AVIATIONSTACK_PER_DAY = int(os.environ.get("BUDGET_AVIATIONSTACK_PER_DAY", "1000"))
BUDGET_OPENSKY_PER_DAY = int(os.environ.get("BUDGET_OPENSKY_PER_DAY", "380"))