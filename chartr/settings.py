from pathlib import Path
import os
from decouple import config


BASE_DIR = Path(__file__).resolve().parent.parent  # repo root (where manage.py lives)

# --- Core ---
SECRET_KEY = config("SECRET_KEY", default="insecure-change-me")
DEBUG = bool(int(config("DEBUG", default="1")))
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*,localhost,127.0.0.1").split(",")

# Render provides the external hostname via this env var — trust it automatically.
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CRYPTOCOMPARE_API_KEY = config(
    "CRYPTOCOMPARE_API_KEY",
    default="ffe54c0c549c51a5c51906b012c19685239dc62e5465478c7c30dea7c76e959e",
)

# --- Apps ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "corsheaders",
    # your apps
    "core",
]
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# --- Middleware (WhiteNoise for static files in container) ---
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serve static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.nav_context",
            ],
        },
    },
]

WSGI_APPLICATION = "chartr.wsgi.application"

from dotenv import load_dotenv

load_dotenv()

# Database resolution order:
#   1. DATABASE_URL (Render / Postgres, e.g. postgres://user:pass@host:5432/db)
#   2. DB_ENGINE=mysql  (legacy local MySQL)
#   3. SQLite fallback  (zero-config local dev)
DATABASE_URL = config("DATABASE_URL", default="")
DB_ENGINE = config("DB_ENGINE", default="sqlite")

if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
elif DB_ENGINE == "mysql":
    import pymysql
    pymysql.install_as_MySQLdb()
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": config("DB_NAME", default="chartr"),
            "USER": config("DB_USER", default="root"),
            "PASSWORD": config("DB_PASS", default=""),
            "HOST": config("DB_HOST", default="127.0.0.1"),
            "PORT": config("DB_PORT", default="3306"),
            "OPTIONS": {},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# --- Password validation ---
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N / TZ (Skopje) ---
LANGUAGE_CODE = "mk"
TIME_ZONE = "Europe/Skopje"
USE_I18N = True
USE_TZ = True

# --- Static files (served by WhiteNoise inside container) ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- Security ---
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# Behind Render's proxy, honor the forwarded protocol so HTTPS/CSRF work.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- DRF (minimal) ---
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}
# CACHE - ОВА Е КЛУЧНО ЗА ДА НЕ ГО УДАРАШ CoinGecko секоја секунда!
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "chartr-cache",
        "TIMEOUT": 300,  # 5 минути по default
        "OPTIONS": {
            "MAX_ENTRIES": 1000
        }
    }
}

# Session (за да работи и session-based кеш ако сакаш)
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# --- Logging (optional but handy in Docker) ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

CORS_ALLOW_ALL_ORIGINS = True  # За development (само за тестирање!)