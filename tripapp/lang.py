"""The site language: English, or Hebrew when the family picks it.

The header switch posts to Django's set_language view, which writes the language cookie.
``?lang=he`` (or ``?lang=en``) in any URL does the same, so a shared link can open in Hebrew.
The browser's Accept-Language is NOT used: a family sees English until it presses the switch.
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
        if code not in CODES:
            code = settings.LANGUAGE_CODE
        translation.activate(code)
        request.LANGUAGE_CODE = code
        response = self.get_response(request)
        if asked in CODES:
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, asked, max_age=365 * 24 * 3600, samesite="Lax")
        response.headers.setdefault("Content-Language", code)
        translation.deactivate()
        return response
