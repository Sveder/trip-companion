import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from content_admin.models import Activity
from courses.models import Course, CourseItem
from trips.models import Traveller, Trip

from .models import Clip
from .steps import visible_steps

CLIP_DIR = tempfile.mkdtemp(prefix="trip-clips-")
PHONE = "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"


def chopsticks_item(user, ages):
    trip = Trip.objects.create(user=user, destination="japan")
    for a in ages:
        Traveller.objects.create(trip=trip, age=a)
    course = Course.objects.create(trip=trip)
    act = Activity.objects.get(module__slug="chopsticks", type="steps")
    return CourseItem.objects.create(course=course, order=0, activity=act)


@override_settings(CLIP_ROOT=CLIP_DIR)
class ChopsticksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("c@example.com", "c@example.com")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(CLIP_DIR, ignore_errors=True)

    def page(self, item, **headers):
        self.client.force_login(item.course.trip.user)
        r = self.client.get(reverse("activity", args=[item.id]), **headers)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_chopsticks_is_a_ready_steps_activity(self):
        act = Activity.objects.get(module__slug="chopsticks")
        self.assertTrue(act.module.ready)
        self.assertEqual([s["kind"] for s in act.data["steps"]], ["link", "video", "text", "record"])

    def test_referral_step_only_with_a_child(self):
        family = self.page(chopsticks_item(self.user, [38, 4]), HTTP_USER_AGENT=PHONE)
        self.assertIn("aliexpress.com", family)
        adults = self.page(chopsticks_item(self.user, [40, 38]), HTTP_USER_AGENT=PHONE)
        self.assertNotIn("aliexpress.com", adults)
        self.assertNotIn("kids' chopsticks", adults)

    def test_unapproved_video_never_renders(self):
        item = chopsticks_item(self.user, [38, 4])
        vid = next(s for s in item.activity.data["steps"] if s["kind"] == "video")
        self.assertFalse(vid["approved"])
        html = self.page(item, HTTP_USER_AGENT=PHONE)
        self.assertNotIn(vid["youtube"], html)
        self.assertNotIn("youtube", html)
        self.assertIn("data-video-fallback", html)

    def test_approved_video_renders_from_nocookie(self):
        item = chopsticks_item(self.user, [38, 4])
        data = dict(item.activity.data)
        data["steps"] = [dict(s, approved=True) if s["kind"] == "video" else s for s in data["steps"]]
        item.activity.data = data
        item.activity.save()
        html = self.page(item, HTTP_USER_AGENT=PHONE)
        self.assertIn("https://www.youtube-nocookie.com/embed/CBNw5yX1M34", html)
        self.assertNotIn("data-video-fallback", html)

    def test_bad_video_id_is_dropped_even_if_approved(self):
        trip = Trip.objects.create(user=self.user)
        steps = visible_steps({"steps": [{"kind": "video", "youtube": '"><script>', "approved": True}]}, trip)
        self.assertFalse(steps[0]["show_video"])
        self.assertNotIn("youtube", steps[0])

    def test_tv_shows_do_it_on_the_phone_and_no_recorder(self):
        html = self.page(chopsticks_item(self.user, [38, 4]), HTTP_USER_AGENT="Mozilla/5.0 (Web0S; Linux/SmartTV)")
        self.assertIn("Do this part on your phone", html)
        self.assertNotIn("data-no-camera hidden", html)
        self.assertNotIn("data-recorder", html)
        self.assertIn("We did it!", html)

    def test_phone_gets_recorder_with_fallback_hidden(self):
        html = self.page(chopsticks_item(self.user, [38, 4]), HTTP_USER_AGENT=PHONE)
        self.assertIn("data-recorder", html)
        self.assertIn("data-no-camera hidden", html)
        self.assertIn("js/record.js", html)

    def test_saved_clip_is_in_the_database_and_private(self):
        item = chopsticks_item(self.user, [38, 4])
        self.client.force_login(self.user)
        clip = SimpleUploadedFile("x.webm", b"\x1aE\xdf\xa3fakewebm", content_type="video/webm;codecs=vp8,opus")
        r = self.client.post(reverse("clip_save", args=[item.id]), {"clip": clip})
        self.assertEqual(r.status_code, 200, r.content)
        saved = Clip.objects.get(id=r.json()["id"])
        self.assertEqual((saved.trip, saved.item, saved.content_type), (item.course.trip, item, "video/webm"))
        self.assertTrue(saved.file.name.endswith(".webm"))
        self.assertTrue(saved.file.path.startswith(CLIP_DIR))
        self.assertEqual(self.client.get(r.json()["url"]).status_code, 200)
        other = get_user_model().objects.create_user("o@example.com", "o@example.com")
        self.client.force_login(other)
        self.assertEqual(self.client.get(r.json()["url"]).status_code, 404)
        self.assertEqual(self.client.post(reverse("clip_save", args=[item.id]), {"clip": clip}).status_code, 404)

    def test_clip_must_be_a_video(self):
        item = chopsticks_item(self.user, [38, 4])
        self.client.force_login(self.user)
        r = self.client.post(reverse("clip_save", args=[item.id]), {"clip": SimpleUploadedFile("x.html", b"<b>", content_type="text/html")})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Clip.objects.exists())
