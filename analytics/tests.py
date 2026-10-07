import re
from urllib.parse import urlsplit
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from activities.tests import CLIP_DIR, chopsticks_item
from content_admin.models import Module
from courses.models import Course
from reminders.logic import build_email

from .models import NAMES, Event, track


class EventTests(TestCase):
    """Each action a family takes writes exactly one event of its own name."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def assertOne(self, name, **data):
        events = Event.objects.filter(name=name)
        self.assertEqual(events.count(), 1, f"{name}: {list(Event.objects.values_list('name', flat=True))}")
        for k, v in data.items():
            self.assertEqual(events.get().data.get(k), v)
        return events.get()

    def test_journey_writes_one_event_per_action(self):
        c = self.client
        c.post(reverse("signin"), {"email": "fam@example.com"})
        self.assertOne("signed_up")
        code = re.search(r"code is:\s+(\S+)", mail.outbox[0].body).group(1)
        c.post(reverse("account_confirm_login_code"), {"code": code})
        self.assertOne("signed_in")

        start = date.today() + timedelta(days=30)
        c.post(reverse("trip_setup"), {"destination": "japan", "ages": "38, 4",
                                       "start_date": start, "end_date": start + timedelta(days=10)})
        self.assertOne("trip_set_up", new=True, travellers=2)

        ids = [str(m.id) for m in Module.objects.filter(slug__in=["food", "chopsticks"])]
        c.post(reverse("builder"), {"modules": ids})
        self.assertOne("course_built", rebuild=False)
        self.assertFalse(Event.objects.filter(name__in=["module_added", "module_removed"]).exists())

        course = Course.objects.get()
        first = course.items.first()
        c.get(reverse("activity", args=[first.id]))
        self.assertOne("activity_opened", activity=first.activity_id)
        c.post(reverse("activity_done", args=[first.id]))
        self.assertOne("activity_done", activity=first.activity_id)
        c.post(reverse("activity_done", args=[first.id]))  # a second press counts once
        self.assertOne("activity_done")

        c.get(reverse("quiz"))
        c.post(reverse("quiz"), {"key": self.client.session["quiz"]["keys"][0], "choice": "nope"})
        self.assertOne("quiz_answer", right=False)

        sticks = course.items.get(activity__module__slug="chopsticks")
        c.get(reverse("go", args=[sticks.id, "kids-chopsticks"]))
        self.assertOne("referral_click", link="kids-chopsticks")
        r = c.post(reverse("track_video", args=[sticks.id]), {"video": "CBNw5yX1M34"})
        self.assertEqual(r.status_code, 204)
        self.assertOne("video_play", video="CBNw5yX1M34")
        with override_settings(CLIP_ROOT=CLIP_DIR):
            clip = SimpleUploadedFile("c.webm", b"x" * 100, content_type="video/webm")
            c.post(reverse("clip_save", args=[sticks.id]), {"clip": clip})
        self.assertOne("clip_saved", size=100)

        # Rebuild without chopsticks, with the words module.
        words = Module.objects.get(slug="words")
        food = Module.objects.get(slug="food")
        c.post(reverse("builder"), {"modules": [str(food.id), str(words.id)]})
        self.assertEqual(Event.objects.filter(name="course_built").count(), 2)
        self.assertOne("module_added", module=words.id)
        self.assertOne("module_removed", module=Module.objects.get(slug="chopsticks").id)

        # Every event of the journey belongs to this family.
        user = get_user_model().objects.get(email="fam@example.com")
        self.assertFalse(Event.objects.exclude(user=user).exists())

    def test_reminder_link_counts_a_click(self):
        item = chopsticks_item(get_user_model().objects.create_user("r@example.com", "r@example.com"), [38, 4])
        link = re.search(r"https?://\S+", build_email(item.course.trip.user, item).body).group(0)
        self.assertIn("?from=reminder", link)
        self.client.force_login(item.course.trip.user)
        parts = urlsplit(link)
        self.client.get(f"{parts.path}?{parts.query}")
        self.assertOne("reminder_click")
        self.assertOne("activity_opened")

    def test_video_beacon_is_private(self):
        item = chopsticks_item(get_user_model().objects.create_user("v@example.com", "v@example.com"), [4])
        self.client.force_login(get_user_model().objects.create_user("x@example.com", "x@example.com"))
        self.assertEqual(self.client.post(reverse("track_video", args=[item.id])).status_code, 404)
        self.assertFalse(Event.objects.exists())

    def test_unknown_name_is_a_bug(self):
        with self.assertRaises(ValueError):
            track("made_up")

    def test_every_name_has_a_label(self):
        self.assertTrue(all(NAMES.values()))


class StatsPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        User = get_user_model()
        cls.staff = User.objects.create_user("boss@example.com", "boss@example.com", is_staff=True)
        cls.parent = User.objects.create_user("p@example.com", "p@example.com")

    def test_non_staff_gets_403(self):
        self.client.force_login(self.parent)
        self.assertEqual(self.client.get(reverse("stats")).status_code, 403)

    def test_signed_out_goes_to_sign_in(self):
        r = self.client.get(reverse("stats"))
        self.assertEqual(r.status_code, 302)

    def test_staff_sees_funnel_and_daily_totals(self):
        item = chopsticks_item(self.parent, [38, 4])
        trip = item.course.trip
        trip.start_date = date.today() + timedelta(days=20)
        trip.save()
        item.mark_done()
        track("activity_done", trip=trip)
        track("referral_click", trip=trip, link="kids-chopsticks")
        track("referral_click", trip=trip, link="kids-chopsticks")
        self.client.force_login(self.staff)
        r = self.client.get(reverse("stats"))
        self.assertEqual(r.status_code, 200)
        funnel = {s["label"]: s["count"] for s in r.context["funnel"]}
        self.assertEqual(funnel, {"Signed up": 2, "Trip set up": 1, "Course built": 1,
                                  "First activity done": 1, "3 activities done": 0})
        self.assertEqual(r.context["grand_total"], 3)
        self.assertEqual(r.context["links"], [{"link": "kids-chopsticks", "n": 2}])
        html = r.content.decode()
        self.assertIn("<tfoot>", html)
        self.assertIn("Shop link clicked", html)
