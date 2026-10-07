from django.urls import path

from . import views

urlpatterns = [path("trip/", views.trip_setup, name="trip_setup")]
