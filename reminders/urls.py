from django.urls import path

from . import views

urlpatterns = [path("reminders/stop/<str:token>/", views.stop, name="reminders_stop")]
