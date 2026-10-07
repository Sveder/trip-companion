"""Site-wide pages: privacy, the favicon, and the share-preview and Sentry settings for every page."""
from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views.decorators.cache import cache_control


def privacy(request):
    return render(request, "privacy.html")


@cache_control(max_age=60 * 60 * 24)
def favicon(request):
    path = finders.find("img/favicon.ico")
    if not path:
        raise Http404
    return FileResponse(open(path, "rb"), content_type="image/x-icon")


def site_meta(request):
    """Share previews need absolute URLs; the Sentry browser loader is on only when its key is set."""
    return {
        "site_url": settings.SITE_URL.rstrip("/"),
        "sentry_js_loader": settings.SENTRY_JS_LOADER,
    }
