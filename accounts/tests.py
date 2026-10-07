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
