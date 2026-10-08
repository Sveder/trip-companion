from django.contrib import admin
from django.urls import include, path

from . import pages

urlpatterns = [
    path("admin/", admin.site.urls),
    path("privacy/", pages.privacy, name="privacy"),
    path("favicon.ico", pages.favicon),
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
