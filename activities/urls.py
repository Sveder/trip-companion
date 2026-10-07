from django.urls import path

from . import views

urlpatterns = [
    path("a/<int:item_id>/", views.activity, name="activity"),
    path("a/<int:item_id>/done/", views.activity_done, name="activity_done"),
    path("a/<int:item_id>/clip/", views.clip_save, name="clip_save"),
    path("clips/<int:clip_id>/", views.clip_file, name="clip"),
]
