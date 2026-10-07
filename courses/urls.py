from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("builder/", views.builder, name="builder"),
    path("highlights/", views.highlights, name="highlights"),
]
