"""Site-wide pages: privacy, the favicon, and the share-preview and Sentry settings for every page."""
from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views.decorators.cache import cache_control


def privacy(request):
    return render(request, "privacy.html")


def credits(request):
    from content_admin.loader import load_photo_credits
    return render(request, "credits.html", {"photos": list(load_photo_credits().values())})


@cache_control(max_age=60 * 60 * 24)
def favicon(request):
    path = finders.find("img/favicon.ico")
    if not path:
        raise Http404
    return FileResponse(open(path, "rb"), content_type="image/x-icon")


def sentry_check(request):
    """Staff only: raise one error, so a person can see that gunicorn errors reach Sentry."""
    if not request.user.is_staff:
        raise Http404
    raise RuntimeError("Sentry check from trip.sveder.com (staff test route)")


def site_meta(request):
    """Share previews need absolute URLs; the Sentry browser loader is on only when its key is set."""
    return {
        "site_url": settings.SITE_URL.rstrip("/"),
        "sentry_js_loader": settings.SENTRY_JS_LOADER,
    }
