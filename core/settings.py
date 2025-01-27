"""
Django settings for core project.

Generated by 'django-admin startproject' using Django 4.1.2.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/
"""

import inspect
import os
import random
import string
from pathlib import Path

from dotenv import load_dotenv
from str2bool import str2bool

load_dotenv()  # take environment variables from .env.

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "".join(random.choice(string.ascii_lowercase) for i in range(32))

# Enable/Disable DEBUG Mode
DEBUG = str2bool(os.environ.get("DEBUG"))
# print(' DEBUG -> ' + str(DEBUG) )

ALLOWED_HOSTS = ["*"]

# Add here your deployment HOSTS
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost",
    "http://127.0.0.1:8000",
    "http://127.0.0.1",
    "https://10.0.10.53",
    "https://41.221.58.50",
]

X_FRAME_OPTIONS = "SAMEORIGIN"

RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Application definition

INSTALLED_APPS = [
    "admin_berry.apps.AdminBerryConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "rest_framework_api_key",
    "jquery",
    "djangoformsetjs",
    "django_celery_beat",
    # Local apps
    "accounts",
    "home",
    "billing",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

HOME_TEMPLATES = os.path.join(BASE_DIR, "templates")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [HOME_TEMPLATES],
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

WSGI_APPLICATION = "core.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

DB_ENGINE = os.environ.get("DB_ENGINE", None)
DB_USERNAME = os.environ.get("DB_USERNAME", None)
DB_PASSWORD = os.environ.get("DB_PASSWORD", None)
DB_HOST = os.environ.get("DB_HOST", None)
DB_PORT = os.environ.get("DB_PORT", None)
DB_NAME = os.environ.get("DB_NAME", None)

if DB_ENGINE and DB_NAME and DB_USERNAME:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends." + DB_ENGINE,
            "NAME": DB_NAME,
            "USER": DB_USERNAME,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
        },
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "db.sqlite3",
        }
    }

# Auth User Model
AUTH_USER_MODEL = "accounts.User"

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Dar_es_Salaam"

USE_I18N = True

USE_TZ = True


# Login URL and Redirect URL
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

# if not DEBUG:
#    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "/"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Cerely Configuration
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Dar_es_Salaam"

# # Redis Configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        # "file": {
        #     "level": "DEBUG",
        #     "class": "logging.FileHandler",
        #     "filename": os.path.join(BASE_DIR, "logs", "celery_tasks.log"),
        # },
        "redis": {
            "level": "DEBUG",
            "class": "core.redis_logging.RedisHandler",
            "host": "redis",
            "port": 6379,
            "key": "django-logs",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["redis"],
            "level": "DEBUG",
            "propagate": True,
        },
        "celery": {
            "handlers": ["redis"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

# GEPG Configurations
####################################################
# GEPG API Headers
GEPG_COM = os.environ.get("GEPG_COM")
GEPG_CODE = os.environ.get("GEPG_CODE")
GEPG_ALG = os.environ.get("GEPG_ALG")

# GEPG SERVER URL
GEPG_URL = os.environ.get("GEPG_URL")

# GEPG API Endpoints
BILL_SUBMISSION = os.environ.get("BILL_SUBMISSION")
RECONCILIATION_REQUEST = os.environ.get("RECONCILIATION_REQUEST")
BILL_CANCELATION = os.environ.get("BILL_CANCELLATION")

# GEPG API Endpoints URL
BILL_SUBMISSION_URL = f"{GEPG_URL}{BILL_SUBMISSION}"
RECONCILIATION_REQUEST_URL = f"{GEPG_URL}{RECONCILIATION_REQUEST}"
BILL_CANCELATION_URL = f"{GEPG_URL}{BILL_CANCELATION}"

# GEPG Bill Parameters
SP_GRP_CODE = os.environ.get("SP_GRP_CODE")
SP_CODE = os.environ.get("SP_CODE")
SUB_SP_CODE = os.environ.get("SUB_SP_CODE")
SP_SYS_ID = os.environ.get("SP_SYS_ID")

GEPG_PUBLIC_KEY = os.environ.get("GEPG_PUBLIC_KEY")
GEPG_PUBLIC_KEY_PASSWORD = os.environ.get("GEPG_PUBLIC_KEY_PASSWORD")

# Encryption Key
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
ENCRYPTION_KEY_PASSWORD = os.environ.get("ENCRYPTION_KEY_PASSWORD")

# Exchange Rate Endpoint
EXCRATES_URL = os.environ.get("EXCRATES_URL")

# Email Configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = os.environ.get("EMAIL_PORT")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS")

# Support Email
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL")
DEVELOPER_EMAIL = os.environ.get("DEVELOPER_EMAIL")
