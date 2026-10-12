"""Django settings for Trip Companion."""
import os
import sys
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
    "tripapp.security.ContentSecurityPolicyMiddleware",
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
                "tripapp.guides.country_guide",
            ],
        },
    },
]

WSGI_APPLICATION = "tripapp.wsgi.application"

# A file cache, so the two gunicorn workers share rate limits (the /continue/ mail, allauth).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.environ.get("DJANGO_CACHE_DIR", str(BASE_DIR / "private" / "cache")),
    }
}

if sys.argv[1:2] == ["test"]:
    # Tests must not share (or wipe) the dev server's file cache. Each rate-limit test clears this one.
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3"),
        # T178: two gunicorn workers write at the same second. A deferred transaction that
        # upgrades a read lock to a write lock fails at once with "database is locked".
        # IMMEDIATE takes the write lock at BEGIN, the timeout makes the second writer wait,
        # and WAL lets readers go on while one worker writes.
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
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
# Production (and STATIC_HASHED=1) serves content-hashed file names; nginx caches them for a year (T229).
# A dev run and the tests keep the plain names, so they need no collectstatic.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "tripapp.storage.HashedStaticStorage"
        if env_bool("STATIC_HASHED", not DEBUG)
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
CLIP_ROOT = Path(os.environ.get("TRIP_CLIP_ROOT", BASE_DIR / "private" / "clips"))
CLIP_MAX_BYTES = 40 * 1024 * 1024
# A phone photo. The page shrinks it in the browser first; this limit is for a browser that cannot.
PHOTO_MAX_BYTES = 25 * 1024 * 1024
# T191: a cap per trip, so one browser cannot fill the disk.
PHOTO_MAX_PER_TRIP = 300
CLIP_MAX_PER_TRIP = 60

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
# T191: a code request for an address with no account sends no mail (the sign-in page cannot spam an inbox).
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = "Trip Companion: "
LOGIN_URL = "signin"
LOGIN_REDIRECT_URL = "home"
ACCOUNT_LOGOUT_REDIRECT_URL = "home"

# No login (feedback T144): every visitor is a guest family held in the session cookie.
# The cookie lives 400 days (the browser maximum) and survives a browser restart.
SESSION_COOKIE_AGE = 400 * 24 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_SAMESITE = "Lax"

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
    if SECRET_KEY == "dev-only-not-secret":
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY: production never runs on the dev key (T191).")
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
# A person's 'manage.py shell' or test run is not production: its errors stay out of Sentry.
# Cron commands (send_reminders) and gunicorn still report.
SENTRY_SKIP_COMMANDS = {"shell", "dbshell", "test", "makemigrations", "showmigrations"}


def sentry_wanted(argv):
    """False when this process is a manage.py command that a person runs by hand."""
    if len(argv) > 1 and os.path.basename(argv[0]) == "manage.py":
        return argv[1] not in SENTRY_SKIP_COMMANDS
    return True


SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
SENTRY_JS_LOADER = os.environ.get("SENTRY_JS_LOADER", "")
if SENTRY_DSN and sentry_wanted(sys.argv):
    import sentry_sdk

    from tripapp.redact import scrub_event

    sentry_sdk.init(
        before_send=scrub_event,
        before_send_transaction=scrub_event,
        dsn=SENTRY_DSN,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )
