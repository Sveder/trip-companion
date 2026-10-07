from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("accounts.urls")),
    path("", include("trips.urls")),
    path("", include("courses.urls")),
    path("", include("activities.urls")),
    path("", include("practice.urls")),
]
