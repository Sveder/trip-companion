"""Continue on another device (feedback T145).

The family types an email. We mail one long link, made once per family and never rotated. Opening the link on
another device logs that browser in to the same family (part 2).
"""
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.contrib import messages
from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from analytics.models import track

from .forms import EmailForm
from .guest import family_required

FAMILY_LIMIT = 3  # sends per family per hour
IP_LIMIT = 10  # sends per IP address per hour
WINDOW = 60 * 60


def contact_for(user):
    from reminders.models import Contact

    contact, _ = Contact.objects.get_or_create(user=user)
    return contact


def link_token(contact):
    """The family's one link token. Made on the first send, then the same forever."""
    if not contact.link_token:
        contact.link_token = secrets.token_urlsafe(32)
        contact.save(update_fields=["link_token"])
    return contact.link_token


def link_url(contact):
    return settings.SITE_URL.rstrip("/") + reverse("continue_open", args=[link_token(contact)])


def owner_of(email):
    """The family that already owns this address (a confirmed user.email), if any."""
    return get_user_model().objects.filter(email__iexact=email).first()


def _over_limit(key, limit):
    cache.add(key, 0, WINDOW)
    try:
        count = cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, WINDOW)
        count = 1
    return count > limit


def _client_ip(request):
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR") or "?"


def send_link(contact, email):
    with translation.override(contact.language or settings.LANGUAGE_CODE):
        ctx = {"url": link_url(contact)}
        subject = render_to_string("accounts/link_subject.txt", ctx).strip()
        body = render_to_string("accounts/link_email.txt", ctx)
    EmailMessage(subject, body, to=[email]).send()
    contact.link_sent_at = timezone.now()
    contact.save(update_fields=["link_sent_at"])


@family_required
def continue_page(request):
    """GET: the one-field form. POST: mail the link. The answer never says if the address had a family."""
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        me = contact_for(request.user)
        if _over_limit(f"continue:family:{request.user.pk}", FAMILY_LIMIT) or \
                _over_limit(f"continue:ip:{_client_ip(request)}", IP_LIMIT):
            return render(request, "accounts/continue.html", {"state": "wait"}, status=429)
        owner = owner_of(email)
        if owner is None:
            me.link_email = email
            me.save(update_fields=["link_email"])
            send_link(me, email)
        elif not (owner.is_staff or owner.is_superuser):
            # The address belongs to a family already (maybe this one). The link goes only to that address.
            send_link(contact_for(owner), email)
        # A staff address gets nothing: a magic link must never open a staff account.
        track("continue_link_sent", user=request.user)
        return render(request, "accounts/continue.html", {"state": "sent", "email": email})
    return render(request, "accounts/continue.html", {"state": "form", "form": form})


def family_for_token(token):
    """The family user of a link token, or None. A staff account never opens by link."""
    from reminders.models import Contact

    if not token or len(token) > 64:
        return None
    contact = Contact.objects.filter(link_token=token).select_related("user").first()
    if contact is None or not contact.user.is_active or contact.user.is_staff or contact.user.is_superuser:
        return None
    return contact


def confirm_email(contact):
    """The link reached the address, so the typed address becomes the family email (reminders start)."""
    user = contact.user
    if user.email or not contact.link_email or owner_of(contact.link_email):
        return
    user.email = contact.link_email
    try:
        with transaction.atomic():
            user.save(update_fields=["email"])
    except IntegrityError:
        user.email = ""


def bind(request, contact):
    """Log this browser in to the linked family. The server wins: a guest family on this browser is left behind."""
    if request.user.is_authenticated and request.user.pk == contact.user_id:
        return False
    login(request, contact.user, backend="django.contrib.auth.backends.ModelBackend")
    track("device_linked", user=contact.user)
    return True


def continue_open(request, token):
    contact = family_for_token(token)
    if contact is None:
        return render(request, "accounts/continue.html", {"state": "bad"}, status=404)
    confirm_email(contact)
    if bind(request, contact):
        messages.success(request, _("Welcome back! This device is connected."))
    return redirect("course")
