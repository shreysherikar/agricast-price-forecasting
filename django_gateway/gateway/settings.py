"""
Django settings for gateway project.
"""
import os
from pathlib import Path
from urllib.parse import urlparse
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in ("true", "1", "yes")

secret_key_env = os.getenv("DJANGO_SECRET_KEY")
if not secret_key_env:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production when DEBUG is False.")
    SECRET_KEY = "insecure-dev-key-change-in-production-way2agribusiness-gateway"
else:
    SECRET_KEY = secret_key_env

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "forecasting.apps.ForecastingConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gateway.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "gateway.wsgi.application"
ASGI_APPLICATION = "gateway.asgi.application"

# Database configuration: PostgreSQL via DATABASE_URL if available, otherwise SQLite
database_url = os.getenv("DJANGO_DATABASE_URL") or os.getenv("DATABASE_URL")

if database_url and ("postgres" in database_url):
    import re
    cleaned_url = re.sub(r"^postgres(ql)?(\+[a-zA-Z0-9_-]+)?://", "postgresql://", database_url)
    parsed = urlparse(cleaned_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "localhost",
            "PORT": parsed.port or 5432,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "gateway.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS configuration
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL", "False").lower() in ("true", "1", "yes")
cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:5173")
if cors_origins_env and not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

# Security hardening when DEBUG is False
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# Django REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

# Cache configuration (1-day cache for forecast responses)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "forecasting-gateway-cache",
        "TIMEOUT": int(os.getenv("FASTAPI_CACHE_TTL_SECONDS", "86400")),
    }
}

# Upstream FastAPI Forecast Service Configuration
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000").rstrip("/")
FASTAPI_TIMEOUT_SECONDS = float(os.getenv("FASTAPI_TIMEOUT_SECONDS", "3.0"))
FASTAPI_CACHE_TTL_SECONDS = int(os.getenv("FASTAPI_CACHE_TTL_SECONDS", "86400"))
