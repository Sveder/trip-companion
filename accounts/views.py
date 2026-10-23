"""The email-code sign-in page. Families no longer need it (T144: guest families); staff use it for the admin.

T191: the page makes no new accounts and mails a code only to an address that has an account. It is rate
limited per address and per IP address, so nobody can use it to flood an inbox.
"""
from allauth.account.internal.flows.login_by_code import LoginCodeVerificationProcess
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model, logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode

from .forms import EmailForm
from .link import client_ip, over_limit

SIGNIN_ADDRESS_LIMIT = 3  # codes per address per hour
SIGNIN_IP_LIMIT = 10  # codes per IP address per hour


def safe_next(request):
    """The ``next`` page from the query, if it is a page on this site."""
    url = request.GET.get("next", "")
    if url and url_has_allowed_host_and_scheme(url, {request.get_host()}, request.is_secure()):
        return url
    return ""


def signin(request):
    next_url = safe_next(request)
    # A guest family is signed in too (T144), so only a staff account skips the form. A guest must be able
    # to sign in as staff here, or the admin cannot be reached from a browser that has used the site.
    if request.user.is_authenticated and request.user.is_staff:
        return redirect(next_url or "home")
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        if over_limit(f"signin:email:{email}", SIGNIN_ADDRESS_LIMIT) or \
                over_limit(f"signin:ip:{client_ip(request)}", SIGNIN_IP_LIMIT):
            return render(request, "accounts/signin.html", {"form": form, "next_url": next_url, "wait": True}, status=429)
        # An unknown address goes to the same code page, so the page does not tell who has an account.
        # ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False: no mail goes to it.
        user = user_for_email(email)
        if request.user.is_authenticated:
            # A guest family session: allauth keeps it signed in after the code, so end it first.
            logout(request)
        LoginCodeVerificationProcess.initiate(request=request, user=user, email=email)
        url = reverse("account_confirm_login_code")
        return redirect(f"{url}?{urlencode({'next': next_url})}" if next_url else url)
    return render(request, "accounts/signin.html", {"form": form, "next_url": next_url})


def user_for_email(email):
    """The account of this address, or None. The old sign-in made a family here; guest families replaced that."""
    address = EmailAddress.objects.filter(email__iexact=email).select_related("user").first()
    if address:
        return address.user
    return get_user_model().objects.filter(email__iexact=email).first()


def make_account(email):
    """The account of this address; a new one when none exists. Only `manage.py make_superuser` makes one now."""
    user = user_for_email(email)
    if user is None:
        user = get_user_model().objects.create_user(username=email[:150], email=email)
        user.set_unusable_password()
        user.save()
    EmailAddress.objects.get_or_create(user=user, email=email, defaults={"primary": True, "verified": False})
    return user
