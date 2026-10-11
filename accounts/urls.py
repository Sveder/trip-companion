from django.urls import path

from . import link, state, views

urlpatterns = [
    path("signin/", views.signin, name="signin"),
    path("state.json", state.state_json, name="state_json"),
    path("state/restore/", state.state_restore, name="state_restore"),
    path("continue/", link.continue_page, name="continue"),
    path("continue/<str:token>/", link.continue_open, name="continue_open"),
]
