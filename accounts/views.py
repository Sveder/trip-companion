"""One sign-in page: type your email, get a code. New emails get an account on the way."""
from allauth.account.internal.flows.login_by_code import LoginCodeVerificationProcess
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render

from .forms import EmailForm


def signin(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        user = user_for_email(email)
        LoginCodeVerificationProcess.initiate(request=request, user=user, email=email)
        return redirect("account_confirm_login_code")
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
