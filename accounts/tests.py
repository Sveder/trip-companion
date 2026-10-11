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


class StateCopyTests(TestCase):
    """T144 part 2: the browser keeps a JSON copy of the family and rebuilds it when the cookie is gone."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command("load_content", verbosity=0)

    def build_family(self):
        from content_admin.models import Module
        from courses.builder import build_course
        from practice.models import PracticeItem
        from trips.models import Traveller, Trip
        self.client.get(reverse("trip_setup"))
        user = get_user_model().objects.get()
        trip = Trip.objects.create(user=user, destination="japan", length_days=10)
        Traveller.objects.create(trip=trip, age=40)
        Traveller.objects.create(trip=trip, age=4)
        course = build_course(trip, list(Module.objects.filter(country="japan").values_list("id", flat=True)))
        items = list(course.ready_items()[:3])
        for item in items:
            item.mark_done()
        PracticeItem.objects.create(trip=trip, key="words/hello/konnichiwa", box=3)
        return items

    def test_state_json_lists_trip_course_and_done_marks(self):
        items = self.build_family()
        state = self.client.get(reverse("state_json")).json()
        self.assertEqual(state["version"], 1)
        self.assertEqual(state["trip"]["length_days"], 10)
        self.assertEqual(sorted(t["age"] for t in state["trip"]["travellers"]), [4, 40])
        keys = {i["key"] for i in state["course"]["items"]}
        self.assertEqual(keys, {f"{i.activity.module.slug}/{i.activity.slug}" for i in items})
        self.assertEqual(state["practice"][0]["box"], 3)

    def test_round_trip_in_a_new_browser_keeps_the_done_marks(self):
        from courses.models import CourseItem
        items = self.build_family()
        state = self.client.get(reverse("state_json")).content
        fresh = self.client_class()
        r = fresh.post(reverse("state_restore"), state, content_type="application/json")
        self.assertEqual(r.json(), {"ok": True})
        self.assertEqual(get_user_model().objects.count(), 2)
        new = get_user_model().objects.exclude(id=items[0].course.trip.user_id).get()
        self.assertTrue(new.username.startswith("family-"))
        done = CourseItem.objects.filter(course__trip__user=new, done_at__isnull=False)
        self.assertEqual({(i.activity_id) for i in done}, {i.activity_id for i in items})
        self.assertEqual(new.trips.get().practice_items.get().box, 3)
        page = fresh.get(reverse("course")).content.decode()
        self.assertIn("3 of", page)
        self.assertEqual(fresh.get(reverse("state_json")).json()["course"]["items"].__len__(), 3)

    def test_a_browser_with_a_family_restores_nothing(self):
        self.build_family()
        state = self.client.get(reverse("state_json")).content
        r = self.client.post(reverse("state_restore"), state, content_type="application/json")
        self.assertFalse(r.json()["ok"])
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_an_empty_guest_gets_the_copy(self):
        items = self.build_family()
        state = self.client.get(reverse("state_json")).content
        fresh = self.client_class()
        fresh.get(reverse("course"))  # the cookies are gone; a family page makes an empty guest first
        self.assertEqual(get_user_model().objects.count(), 2)
        r = fresh.post(reverse("state_restore"), state, content_type="application/json")
        self.assertEqual(r.json(), {"ok": True})
        self.assertEqual(get_user_model().objects.count(), 2)
        self.assertEqual(len(fresh.get(reverse("state_json")).json()["course"]["items"]), len(items))

    def test_staff_is_never_overwritten(self):
        staff = get_user_model().objects.create_user("s@example.com", "s@example.com", is_staff=True)
        self.client.force_login(staff)
        r = self.client.post(reverse("state_restore"), b'{"version": 1, "trip": {"travellers": []}}', content_type="application/json")
        self.assertFalse(r.json()["ok"])
        self.assertFalse(staff.trips.exists())

    def test_bad_body_is_400_and_makes_no_family(self):
        for body in (b"not json", b"[1, 2]", b'{"version": 9}', b'{"version": 1, "x": "' + b"a" * 70000 + b'"}'):
            r = self.client_class().post(reverse("state_restore"), body, content_type="application/json")
            self.assertEqual(r.status_code, 400, body[:20])
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_unknown_modules_and_bad_values_are_skipped(self):
        body = {"version": 1, "language": "he", "trip": {"destination": "japan", "length_days": "x", "travellers": [{"age": 7}, {"age": -3}]},
                "course": {"modules": ["food", "no-such-module"], "items": [{"key": "nope/nope", "done_at": "2026-10-01T10:00:00Z"}]},
                "practice": [{"key": 5}, {"key": "a/b/c", "box": 99, "due_on": "bad"}]}
        import json
        fresh = self.client_class()
        r = fresh.post(reverse("state_restore"), json.dumps(body), content_type="application/json")
        self.assertEqual(r.json(), {"ok": True})
        trip = get_user_model().objects.get().trips.get()
        self.assertEqual(trip.ages, [7])
        self.assertIsNone(trip.length_days)
        self.assertEqual(trip.practice_items.get().box, 10)
        self.assertEqual(r.cookies["django_language"].value, "he")

    def test_pages_say_if_the_browser_has_a_family(self):
        self.assertContains(self.client.get(reverse("privacy")), 'data-family="0"')
        self.assertContains(self.client.get(reverse("trip_setup")), 'data-family="1"')
        self.assertContains(self.client.get(reverse("trip_setup")), "js/state.js")
