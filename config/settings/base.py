import os
from pathlib import Path
from decouple import config
import dj_database_url

# config/settings/base.py está 3 niveles abajo de la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Leemos SECRET_KEY y FERNET_KEY directo de os.environ para evitar
# que python-decouple los busque en archivos .env inexistentes en producción
SECRET_KEY = os.environ.get("SECRET_KEY") or config("SECRET_KEY", default="django-insecure-change-this-in-production-please")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*").split(",")
CSRF_TRUSTED_ORIGINS = ["https://stockia-production-c8b1.up.railway.app"]

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

PROJECT_APPS = [
    "apps.catalogo",
    "apps.inventario",
    "apps.ventas",
    "apps.inteligencia",
    "apps.identidad",
]

INSTALLED_APPS = DJANGO_APPS + PROJECT_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de datos — Railway inyecta DATABASE_URL automáticamente
DATABASES = {
    "default": dj_database_url.config(default=os.environ.get("DATABASE_URL", ""))
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Almacenamiento de archivos ────────────────────────────────────────────────
# En producción (Railway) se usa Cloudinary para persistir las imágenes entre deploys.
# En local sin CLOUDINARY_URL se usa el filesystem normal.
_CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "")
if _CLOUDINARY_URL:
    INSTALLED_APPS += ["cloudinary", "cloudinary_storage"]
    CLOUDINARY_STORAGE = {"CLOUDINARY_URL": _CLOUDINARY_URL}
    STORAGES = {
        "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth
LOGIN_URL = "/identidad/login/"
LOGIN_REDIRECT_URL = "/inventario/"
LOGOUT_REDIRECT_URL = "/identidad/login/"

# Variables propias del proyecto
FERNET_KEY = os.environ["FERNET_KEY"].encode()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
