import re

from allauth.core import context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.test import RequestFactory, TestCase
from django.urls import reverse

from analytics.models import Event


class SignInMessageTests(TestCase):
    """Sign-in shows one short friendly line, not allauth's grown-up banners."""

    def test_code_page_has_no_banner(self):
        r = self.client.post("/signin/", {"email": "kid@example.com"}, follow=True)
        self.assertContains(r, "We sent a code to")
        self.assertNotContains(r, "A sign-in code has been sent")
        self.assertNotContains(r, 'class="messages"')

    def test_one_friendly_line_after_code(self):
        self.client.post("/signin/", {"email": "kid@example.com"})
        code = mail.outbox[-1].body.split("code is:")[1].split()[0]
        r = self.client.post(reverse("account_confirm_login_code"), {"code": code}, follow=True)
        texts = [str(m) for m in get_messages(r.wsgi_request)] or re.findall(r'<li class="msg[^"]*">([^<]*)</li>', r.content.decode())
        self.assertEqual(texts, ["Hi! You are in."])
        html = r.content.decode()
        self.assertNotIn("confirmed", html)
        self.assertNotIn("Successfully", html)


class SixDigitCodeTests(TestCase):
    """Michael (feedback #1): the sign-in code is 6 digits, numbers only."""

    def test_email_code_is_six_digits(self):
        for n in range(5):
            self.client.post("/signin/", {"email": f"kid{n}@example.com"})
            code = mail.outbox[-1].body.split("code is:")[1].split()[0]
            self.assertRegex(code, r"^[0-9]{6}$")
            self.client.logout()

    def test_code_box_opens_number_pad(self):
        r = self.client.post("/signin/", {"email": "kid@example.com"}, follow=True)
        self.assertContains(r, 'inputmode="numeric"')
        self.assertContains(r, 'maxlength="6"')
        self.assertContains(r, "Your 6-digit code")

    def test_six_digit_code_signs_in(self):
        self.client.post("/signin/", {"email": "kid@example.com"})
        code = mail.outbox[-1].body.split("code is:")[1].split()[0]
        r = self.client.post(reverse("account_confirm_login_code"), {"code": code}, follow=True)
        self.assertTrue(r.wsgi_request.user.is_authenticated)


GOOGLE_ON = {
    "GOOGLE_CLIENT_ID": "test-client.apps.googleusercontent.com",
    "SOCIALACCOUNT_PROVIDERS": {
        "google": {
            "APPS": [{"client_id": "test-client.apps.googleusercontent.com", "secret": "test-secret"}],
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {"prompt": "select_account"},
            "EMAIL_AUTHENTICATION": True,
        }
    },
}


class GoogleSignInTests(TestCase):
    """Feedback T81: 'Sign in with Google' next to the email code."""

    def test_no_button_without_keys(self):
        with self.settings(GOOGLE_CLIENT_ID=""):
            r = self.client.get("/signin/")
        self.assertNotContains(r, "Sign in with Google")

    def test_button_posts_to_google_login(self):
        with self.settings(**GOOGLE_ON):
            r = self.client.get("/signin/?next=/course/")
        self.assertContains(r, "Sign in with Google")
        self.assertContains(r, 'action="/accounts/google/login/?next=%2Fcourse%2F"')

    def test_button_in_hebrew(self):
        with self.settings(**GOOGLE_ON):
            self.client.cookies["django_language"] = "he"
            r = self.client.get("/signin/", HTTP_ACCEPT_LANGUAGE="he")
        self.assertContains(r, "כניסה עם Google")

    def test_login_sends_the_family_to_google(self):
        with self.settings(**GOOGLE_ON):
            r = self.client.post("/accounts/google/login/")
        self.assertEqual(r.status_code, 302)
        url = r["Location"]
        self.assertTrue(url.startswith("https://accounts.google.com/o/oauth2/"), url)
        self.assertIn("client_id=test-client.apps.googleusercontent.com", url)
        self.assertIn("redirect_uri=http%3A%2F%2Ftestserver%2Faccounts%2Fgoogle%2Flogin%2Fcallback%2F", url)
        self.assertIn("prompt=select_account", url)


class GoogleSameAccountTests(TestCase):
    """A family that signed in by email code and then uses Google lands in the same account."""

    def google_login(self, email):
        """Run allauth's real login flow with the answer Google gives after the consent screen."""
        request = RequestFactory().get("/accounts/google/login/callback/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        request.user = AnonymousUser()
        with context.request_context(request):
            provider = get_social_adapter().get_provider(request, "google")
            login = provider.sociallogin_from_response(
                request, {"sub": "g-" + email, "email": email, "email_verified": True, "name": "Test"}
            )
            complete_social_login(request, login)
        return request

    def test_existing_email_user_is_reused(self):
        self.client.post("/signin/", {"email": "mom@example.com"})
        old = get_user_model().objects.get(email="mom@example.com")
        with self.settings(**GOOGLE_ON):
            request = self.google_login("mom@example.com")
        self.assertEqual(request.user.pk, old.pk)
        self.assertEqual(get_user_model().objects.filter(email__iexact="mom@example.com").count(), 1)
        self.assertTrue(SocialAccount.objects.filter(user=old, provider="google").exists())

    def test_new_google_user_gets_an_account(self):
        with self.settings(**GOOGLE_ON):
            request = self.google_login("dad@example.com")
        user = get_user_model().objects.get(email="dad@example.com")
        self.assertEqual(request.user.pk, user.pk)
        self.assertTrue(Event.objects.filter(name="signed_up", user=user, data__method="google").exists())
