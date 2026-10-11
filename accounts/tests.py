import re

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase
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


class GuestFamilyTests(TestCase):
    """Feedback T144: no login. Anyone opens the site, builds a course and plays."""

    def test_fresh_browser_reaches_trip_setup(self):
        User = get_user_model()
        r = self.client.get(reverse("trip_setup"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        guest = User.objects.get()
        self.assertEqual(guest.email, "")
        self.assertFalse(guest.has_usable_password())
        self.assertTrue(guest.username.startswith("family-"))
        self.assertTrue(Event.objects.filter(name="signed_up", user=guest, data__method="guest").exists())

    def test_two_requests_share_one_family(self):
        self.client.get(reverse("trip_setup"))
        self.client.get(reverse("trip_setup"))
        self.client.get(reverse("course"))
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_two_browsers_get_two_families(self):
        self.client.get(reverse("trip_setup"))
        self.client_class().get(reverse("trip_setup"))
        self.assertEqual(get_user_model().objects.count(), 2)

    def test_guest_keeps_the_language(self):
        from reminders.models import Contact
        self.client.cookies["django_language"] = "he"
        self.client.get(reverse("trip_setup"), HTTP_ACCEPT_LANGUAGE="he")
        self.assertEqual(Contact.objects.get().language, "he")

    def test_session_cookie_lasts_400_days(self):
        r = self.client.get(reverse("trip_setup"))
        self.assertEqual(r.cookies["sessionid"]["max-age"], 400 * 24 * 60 * 60)

    def test_stats_is_403_for_a_guest(self):
        self.client.get(reverse("trip_setup"))
        self.assertEqual(self.client.get(reverse("stats")).status_code, 403)

    def test_no_page_offers_sign_in_or_sign_out(self):
        for lang in ("en", "he"):
            self.client.cookies["django_language"] = lang
            html = self.client.get("/").content.decode()
            self.assertNotIn("/signin/", html)
            self.assertNotIn("Sign in", html)
        html = self.client.get(reverse("trip_setup")).content.decode()
        self.assertNotIn("/signin/", html)
        self.assertNotIn("Sign out", html)

    def test_guest_gets_no_reminder(self):
        from reminders.logic import due
        self.client.get(reverse("trip_setup"))
        self.assertIsNone(due(get_user_model().objects.get()))


class NoGoogleTests(TestCase):
    """Feedback T152: Sign in with Google is gone."""

    def test_sign_in_page_has_no_google(self):
        self.assertNotContains(self.client.get("/signin/"), "Google")

    def test_google_login_url_is_gone(self):
        self.assertEqual(self.client.post("/accounts/google/login/").status_code, 404)
