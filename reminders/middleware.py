from datetime import timedelta

from django.utils import timezone

from .models import Contact

# Write the visit time at most once an hour per family.
SEEN_EVERY = timedelta(hours=1)


class LastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = timezone.now()
            contact, _ = Contact.objects.get_or_create(user=user)
            if contact.last_seen is None or now - contact.last_seen >= SEEN_EVERY:
                contact.last_seen = now
                contact.save(update_fields=["last_seen"])
        return self.get_response(request)
