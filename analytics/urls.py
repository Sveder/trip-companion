from django.urls import path

from . import views

urlpatterns = [
    path("stats/", views.stats, name="stats"),
    path("t/video/<int:item_id>/", views.video_play, name="track_video"),
]
