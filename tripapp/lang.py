"""The site language: English, or Hebrew when the family picks it.

The header switch posts to Django's set_language view, which writes the language cookie.
``?lang=he`` (or ``?lang=en``) in any URL does the same, so a shared link can open in Hebrew.
The browser's Accept-Language is NOT used: a family sees English until it presses the switch.
A signed-in family on a new device (no cookie, no ?lang) gets its saved language (Contact.language),
and the cookie is set from it. ``request.LANGUAGE_CHOSEN`` is True only when the family chose the language
(?lang, the cookie, or the switch POST); only then may LastSeenMiddleware save it (T127).
"""
from django.conf import settings
from django.utils import translation

CODES = {code for code, _ in settings.LANGUAGES}


class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        asked = request.GET.get("lang")
        code = asked if asked in CODES else request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        chosen = code in CODES
        remember = asked if asked in CODES else None
        if not chosen:
            code = saved_language(request) or settings.LANGUAGE_CODE
            if code != settings.LANGUAGE_CODE:
                remember = code
        translation.activate(code)
        request.LANGUAGE_CODE = code
        request.LANGUAGE_CHOSEN = chosen
        response = self.get_response(request)
        if remember and settings.LANGUAGE_COOKIE_NAME not in response.cookies:  # the switch view sets its own
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, remember, max_age=365 * 24 * 3600, samesite="Lax")
        response.headers.setdefault("Content-Language", code)
        translation.deactivate()
        return response


def saved_language(request):
    """The language a signed-in family chose before, on any device. None for a visitor."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    from reminders.models import Contact

    code = Contact.objects.filter(user=user).values_list("language", flat=True).first()
    return code if code in CODES else None
