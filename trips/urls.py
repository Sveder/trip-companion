from django.urls import path

from . import views

urlpatterns = [
    path("trip/", views.trip_setup, name="trip_setup"),
    path("trip/in-japan/", views.in_japan_now, name="in_japan_now"),
]
