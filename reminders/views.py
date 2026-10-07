from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from .logic import user_from_token
from .models import Contact


def stop(request, token):
    """GET asks, POST stops. A mail scanner that opens the link changes nothing."""
    pk = user_from_token(token)
    user = get_user_model().objects.filter(pk=pk).first() if pk is not None else None
    if user is None:
        raise Http404
    contact, _ = Contact.objects.get_or_create(user=user)
    if request.method == "POST":
        if request.POST.get("again") == "1":
            contact.unsubscribed_at = None
        elif contact.unsubscribed_at is None:
            contact.unsubscribed_at = timezone.now()
        contact.save(update_fields=["unsubscribed_at"])
    return render(request, "reminders/stop.html", {"stopped": contact.unsubscribed_at is not None})
