"""One sign-in page: type your email, get a code. New emails get an account on the way."""
from allauth.account.internal.flows.login_by_code import LoginCodeVerificationProcess
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode

from .forms import EmailForm


def safe_next(request):
    """The ``next`` page from the query, if it is a page on this site."""
    url = request.GET.get("next", "")
    if url and url_has_allowed_host_and_scheme(url, {request.get_host()}, request.is_secure()):
        return url
    return ""


def signin(request):
    next_url = safe_next(request)
    if request.user.is_authenticated:
        return redirect(next_url or "home")
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        user = user_for_email(email)
        LoginCodeVerificationProcess.initiate(request=request, user=user, email=email)
        url = reverse("account_confirm_login_code")
        return redirect(f"{url}?{urlencode({'next': next_url})}" if next_url else url)
    return render(request, "accounts/signin.html", {"form": form})


def user_for_email(email):
    User = get_user_model()
    address = EmailAddress.objects.filter(email__iexact=email).select_related("user").first()
    if address:
        return address.user
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(username=email[:150], email=email)
        user.set_unusable_password()
        user.save()
    EmailAddress.objects.get_or_create(user=user, email=email, defaults={"primary": True, "verified": False})
    return user
