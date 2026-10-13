from django.contrib import admin
from django.urls import include, path

from . import pages

urlpatterns = [
    path("admin/", admin.site.urls),
    path("privacy/", pages.privacy, name="privacy"),
    path("safety/", pages.safety, name="safety"),
    path("safety/<slug:country>/", pages.safety, name="safety_country"),
    path("safety-card/", pages.safety_card, name="safety_card"),
    path("credits/", pages.credits, name="credits"),
    path("favicon.ico", pages.favicon),
    path("robots.txt", pages.robots_txt),
    path("staff/sentry-check/", pages.sentry_check),
    path("i18n/", include("django.conf.urls.i18n")),
    path("accounts/", include("allauth.urls")),
    path("", include("accounts.urls")),
    path("", include("trips.urls")),
    path("", include("courses.urls")),
    path("", include("activities.urls")),
    path("", include("practice.urls")),
    path("", include("reminders.urls")),
    path("", include("analytics.urls")),
    path("", include("there.urls")),
]
