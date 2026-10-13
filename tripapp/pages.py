"""Site-wide pages: privacy, the favicon, and the share-preview and Sentry settings for every page."""
from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views.decorators.cache import cache_control


def privacy(request):
    return render(request, "privacy.html")


def safety_card(request):
    """T277: the child safety card. The form has no action and its fields have no name, so nothing in it reaches
    the server. static/js/safety_card.js draws the card and writes the PDF in the browser."""
    return render(request, "safety_card.html")


def safety(request, country=None):
    """T279 (Michael): one page per country with the important safety things: the emergency numbers, where to find
    help, the lost-child plan, the earthquake note and the safety card. Open to everyone; with no country in the URL
    it shows the family's own country, else Japan."""
    from content_admin.i18n import localize
    from content_admin.loader import load_safety_overview
    from trips.models import active_trip

    pages = load_safety_overview()
    if country is None:
        trip = active_trip(request.user) if request.user.is_authenticated else None
        country = trip.destination if trip and trip.destination in pages else "japan"
    if country not in pages:
        raise Http404
    return render(request, "safety.html", {"page": localize(pages[country]), "country": country})


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
