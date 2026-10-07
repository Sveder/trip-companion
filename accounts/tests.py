import re

from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase
from django.urls import reverse


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
