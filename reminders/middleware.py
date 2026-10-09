from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from tripapp.lang import CODES

from .models import Contact

# Write the visit time at most once an hour per family. The language is written as soon as it changes,
# but only when the family chose it (?lang, the cookie, the switch): never the English default of a new device.
SEEN_EVERY = timedelta(hours=1)


class LastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = timezone.now()
            contact, _ = Contact.objects.get_or_create(user=user)
            fields = []
            if contact.last_seen is None or now - contact.last_seen >= SEEN_EVERY:
                contact.last_seen = now
                fields.append("last_seen")
            language = chosen_language(request)
            if language and language != contact.language:
                contact.language = language
                fields.append("language")
            if fields:
                contact.save(update_fields=fields)
        return self.get_response(request)


def chosen_language(request):
    """The language the family chose on this request, or None when the page only shows a default."""
    if request.method == "POST" and request.path == reverse("set_language"):
        code = request.POST.get("language")
        return code if code in CODES else None
    if getattr(request, "LANGUAGE_CHOSEN", False):
        return getattr(request, "LANGUAGE_CODE", None)
    return None
