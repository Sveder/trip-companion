"""The admin uses the site's own email-code sign-in instead of a password form."""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode


def admin_login(request, extra_context=None):
    next_url = request.GET.get("next") or reverse("admin:index")
    if request.user.is_authenticated:
        # Signed in but not staff: the admin is not for this account.
        return redirect("home") if not request.user.is_staff else redirect(next_url)
    return redirect(f"{reverse('signin')}?{urlencode({'next': next_url})}")


def setup():
    admin.site.site_header = "Trip Companion admin"
    admin.site.site_title = "Trip Companion admin"
    admin.site.index_title = "Content, trips and families"
    admin.site.login = admin_login
