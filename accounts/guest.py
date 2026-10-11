"""No login (feedback T144): every visitor is a guest family, kept in a long-lived session cookie."""
import secrets
from functools import wraps

from django.contrib.auth import get_user_model, login

from analytics.models import track

GUEST_PREFIX = "family-"


def ensure_family(request):
    """The family of this browser. A first visit makes a new guest family and logs the browser in."""
    if request.user.is_authenticated:
        return request.user
    from reminders.models import Contact

    User = get_user_model()
    user = User(username=GUEST_PREFIX + secrets.token_hex(6), email="")
    user.set_unusable_password()
    user.save()
    Contact.objects.create(user=user, language=getattr(request, "LANGUAGE_CODE", None) or "en")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    track("signed_up", user=user, method="guest")
    return user


def is_guest(user):
    return user.is_authenticated and not user.email and user.username.startswith(GUEST_PREFIX)


def family_required(view):
    """Like login_required, but a visitor with no family gets one instead of a sign-in page."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        ensure_family(request)
        return view(request, *args, **kwargs)
    return wrapper
