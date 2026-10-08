from datetime import timedelta

from django.utils import timezone

from .models import Contact

# Write the visit time at most once an hour per family. The language is written as soon as it changes.
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
            language = getattr(request, "LANGUAGE_CODE", None)
            if language and language != contact.language:
                contact.language = language
                fields.append("language")
            if fields:
                contact.save(update_fields=fields)
        return self.get_response(request)
