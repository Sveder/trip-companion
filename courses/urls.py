from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("next/", views.next_step, name="next_step"),
    path("course/", views.course, name="course"),
    path("builder/", views.builder, name="builder"),
    path("highlights/", views.highlights, name="highlights"),
]
