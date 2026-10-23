"""The admin uses the site's own email-code sign-in instead of a password form."""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode


def admin_login(request, extra_context=None):
    next_url = request.GET.get("next") or reverse("admin:index")
    if request.user.is_authenticated and request.user.is_staff:
        return redirect(next_url)
    # Not signed in, or a guest family (T144): the staff email-code sign-in.
    return redirect(f"{reverse('signin')}?{urlencode({'next': next_url})}")


def setup():
    admin.site.site_header = "Trip Companion admin"
    admin.site.site_title = "Trip Companion admin"
    admin.site.index_title = "Content, trips and families"
    admin.site.login = admin_login
