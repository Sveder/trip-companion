from django.urls import path

from . import views

urlpatterns = [
    path("there/", views.hunt, name="there"),
    path("there/<slug:thing>/add/", views.add_photo, name="there_add"),
    path("photos/<int:photo_id>/", views.photo_file, name="photo"),
    path("photos/<int:photo_id>/delete/", views.delete_photo, name="photo_delete"),
]
