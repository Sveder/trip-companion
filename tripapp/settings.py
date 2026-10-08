"""Django settings for Trip Companion."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "content_admin",
    "accounts",
    "trips",
    "courses",
    "activities",
    "practice",
    "reminders",
    "analytics",
    "there",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "tripapp.lang.LanguageMiddleware",
    "tripapp.tv.TvModeMiddleware",
    "reminders.middleware.LastSeenMiddleware",
]

ROOT_URLCONF = "tripapp.urls"

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
                "django.template.context_processors.i18n",
                "tripapp.tv.tv_mode",
                "tripapp.pages.site_meta",
            ],
        },
    },
]

WSGI_APPLICATION = "tripapp.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3"),
    }
}

AUTH_PASSWORD_VALIDATORS = []

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# English is the default. Hebrew only when the family picks it (the switch in the header sets a cookie).
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("he", "עברית")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Jerusalem"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
CLIP_ROOT = Path(os.environ.get("TRIP_CLIP_ROOT", BASE_DIR / "private" / "clips"))
CLIP_MAX_BYTES = 40 * 1024 * 1024
# A phone photo. The page shrinks it in the browser first; this limit is for a browser that cannot.
PHOTO_MAX_BYTES = 25 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Sign-in: the parent types an email and gets a one-time code (allauth "login by code").
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_BY_CODE_TIMEOUT = 15 * 60
# Michael (feedback #1): the code is 6 digits, numbers only, easy to type on a phone.
ACCOUNT_LOGIN_BY_CODE_FORMAT = {"length": 6, "numeric": True, "dashed": False}
ACCOUNT_FORMS = {"confirm_login_code": "accounts.forms.SixDigitCodeForm"}
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = "Trip Companion: "
LOGIN_URL = "signin"
LOGIN_REDIRECT_URL = "home"
ACCOUNT_LOGOUT_REDIRECT_URL = "home"

# Google sign-in (feedback T81). The OAuth client lives in Kurt's Google Cloud project
# trip-companion-511014. The keys come from the server .env only; with no keys the button is hidden.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [{"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET}] if GOOGLE_CLIENT_ID else [],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"prompt": "select_account"},
        # Google checks the address, so a family that first used the email code
        # lands in the same account when it signs in with Google.
        "EMAIL_AUTHENTICATION": True,
    }
}
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_STORE_TOKENS = False

# Absolute links in emails (reminders) start with this.
SITE_URL = os.environ.get("SITE_URL", "https://trip.sveder.com")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Trip Companion <m@sveder.com>")
# SES keys come from the standard AWS chain (~/.aws or AWS_* variables).
if env_bool("EMAIL_SES"):
    EMAIL_BACKEND = "tripapp.ses_backend.SESBackend"
    AWS_SES_REGION = os.environ.get("AWS_SES_REGION", "eu-central-1")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    # trip.sveder.com has no subdomains of its own, so this is safe.
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # Preload works only for the apex domain (sveder.com), not for this subdomain.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Sentry: server errors and slow pages go to Sentry when SENTRY_DSN is set (server .env only).
# The browser loader URL (SENTRY_JS_LOADER) reports browser errors.
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
SENTRY_JS_LOADER = os.environ.get("SENTRY_JS_LOADER", "")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )
