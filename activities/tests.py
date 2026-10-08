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

from .models import Clip, ReferralClick
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
        self.assertIn("/kids-chopsticks/", family)
        adults = self.page(chopsticks_item(self.user, [40, 38]), HTTP_USER_AGENT=PHONE)
        self.assertNotIn("kids-chopsticks", adults)
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


class StreetViewHuntTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("s@example.com", "s@example.com")

    def item(self, slug="streetview-intro"):
        trip = Trip.objects.create(user=self.user, destination="japan")
        Traveller.objects.create(trip=trip, age=5)
        course = Course.objects.create(trip=trip)
        act = Activity.objects.get(module__slug="streetview", slug=slug)
        return CourseItem.objects.create(course=course, order=0, activity=act)

    def setUp(self):
        self.client.force_login(self.user)

    def test_streetview_module_is_ready_with_places(self):
        acts = Activity.objects.filter(module__slug="streetview")
        self.assertTrue(acts[0].module.ready)
        self.assertGreaterEqual(acts.count(), 2)
        for act in acts:
            self.assertEqual(act.type, "streetview")
            self.assertGreaterEqual(len(act.data["spots"]), 3)

    def test_spots_are_japanese_things_not_random_passers_by(self):
        # Michael, feedback 2026-10-08: no "a woman with a pink hat who happened to be there".
        random = ("hat", "people", "cars", "pine tree", "green wall", "shop sign", '"no" sign')
        for act in Activity.objects.filter(module__slug="streetview"):
            for spot in act.data["spots"]:
                for word in random:
                    self.assertNotIn(word, spot["text"].lower(), (act.slug, spot["text"]))
        cats = Activity.objects.get(module__slug="streetview", slug="streetview-intro")
        self.assertIn("lucky cat", cats.data["intro"])

    def test_every_spot_has_a_proper_name_and_why_it_matters(self):
        # Michael, feedback 2026-10-08: "a big orange gate" is a torii gate; say why each thing is interesting.
        for act in Activity.objects.filter(module__slug="streetview"):
            for spot in act.data["spots"]:
                self.assertTrue(spot.get("name"), (act.slug, spot["text"]))
                self.assertGreaterEqual(len(spot.get("about", "")), 40, (act.slug, spot["name"]))
        inari = Activity.objects.get(module__slug="streetview", slug="streetview-inari")
        self.assertIn("Torii gate", [s["name"] for s in inari.data["spots"]])
        html = self.client.get(reverse("activity", args=[self.item("streetview-inari").id])).content.decode()
        self.assertIn('<span class="spot-name">Torii gate</span>', html)
        self.assertIn("the home of a kami", html)

    def test_page_shows_the_embed_and_the_spot_list(self):
        item = self.item()
        r = self.client.get(reverse("activity", args=[item.id]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("https://www.google.com/maps/embed?pb=!6m7!1m6!2m2!1d35.6486000!2d139.6468000!3f120!4f0!5f1", html)
        self.assertNotIn("key=", html)
        self.assertEqual(html.count('name="found"'), 5)
        self.assertIn("A lucky cat with one paw up", html)

    def done(self, item, found):
        return self.client.post(reverse("activity_done", args=[item.id]), {"found": found})

    def test_ticking_some_items_does_not_finish(self):
        item = self.item()
        r = self.done(item, ["0", "1", "2"])
        self.assertRedirects(r, reverse("activity", args=[item.id]) + "?missing=1&found=0,1,2", fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertIsNone(item.done_at)
        self.assertIn("Keep looking", self.client.get(r["Location"]).content.decode())

    def test_ticking_all_items_marks_the_item_done(self):
        item = self.item()
        r = self.done(item, ["0", "1", "2", "3", "4"])
        self.assertRedirects(r, reverse("home"), fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertIsNotNone(item.done_at)

    def test_missing_keeps_the_ticks_and_shows_the_skip_button(self):
        item = self.item()
        r = self.done(item, ["0", "2"])
        html = self.client.get(r["Location"]).content.decode()
        self.assertIn('name="skip"', html)
        self.assertEqual(html.count(" checked>"), 2)
        self.assertNotIn('name="skip"', self.client.get(reverse("activity", args=[item.id])).content.decode())

    def test_skip_after_missing_marks_the_hunt_done_and_home_opens_the_next(self):
        trip = Trip.objects.create(user=self.user, destination="japan")
        Traveller.objects.create(trip=trip, age=3)
        course = Course.objects.create(trip=trip)
        hunts = list(Activity.objects.filter(module__slug="streetview")[:2])
        first = CourseItem.objects.create(course=course, order=0, activity=hunts[0])
        second = CourseItem.objects.create(course=course, order=1, activity=hunts[1])
        url = reverse("activity_done", args=[first.id])
        r = self.client.post(url, {"found": ["0", "1"]})
        self.assertIn("missing=1", r["Location"])
        first.refresh_from_db()
        self.assertIsNone(first.done_at)
        r = self.client.post(url, {"found": ["0", "1"], "skip": "1"})
        first.refresh_from_db()
        self.assertIsNotNone(first.done_at)
        n = len(hunts[0].data["spots"])
        self.assertEqual(r["Location"], reverse("activity_praise", args=[first.id]) + f"?found=2&of={n}")
        self.assertIn(f"You found 2 of {n}!", self.client.get(r["Location"]).content.decode())
        home = self.client.get(reverse("home"))
        self.assertRedirects(home, reverse("activity", args=[second.id]), fetch_redirect_response=False)

    def test_praise_after_a_skip_with_nothing_found_says_good_try(self):
        trip = Trip.objects.create(user=self.user, destination="japan")
        Traveller.objects.create(trip=trip, age=4)
        course = Course.objects.create(trip=trip)
        hunts = list(Activity.objects.filter(module__slug="streetview")[:2])
        first = CourseItem.objects.create(course=course, order=0, activity=hunts[0])
        CourseItem.objects.create(course=course, order=1, activity=hunts[1])
        r = self.client.post(reverse("activity_done", args=[first.id]), {"found": [], "skip": "1"})
        n = len(hunts[0].data["spots"])
        self.assertEqual(r["Location"], reverse("activity_praise", args=[first.id]) + f"?found=0&of={n}")
        html = self.client.get(r["Location"]).content.decode()
        self.assertNotIn("You found 0", html)
        self.assertNotIn("Great job!", html)
        self.assertIn("Good try!", html)
        self.assertIn("look again another day", html)
        html = self.client.get(reverse("activity_praise", args=[first.id]) + f"?found=2&of={n}").content.decode()
        self.assertIn(f"You found 2 of {n}!", html)
        self.assertIn("Great job!", html)

    def test_a_done_hunt_opens_with_no_ticks_and_plays_again(self):
        trip = Trip.objects.create(user=self.user, destination="japan")
        Traveller.objects.create(trip=trip, age=4)
        course = Course.objects.create(trip=trip)
        hunts = list(Activity.objects.filter(module__slug="streetview")[:2])
        first = CourseItem.objects.create(course=course, order=0, activity=hunts[0])
        second = CourseItem.objects.create(course=course, order=1, activity=hunts[1])
        url = reverse("activity_done", args=[first.id])
        self.client.post(url, {"found": [], "skip": "1"})
        first.refresh_from_db()
        done_at = first.done_at
        self.assertIsNotNone(done_at)
        html = self.client.get(reverse("activity", args=[first.id])).content.decode()
        self.assertEqual(html.count(" checked>"), 0)
        self.assertIn("We found them all!", html)
        self.assertNotIn(">Next<", html)
        # On a replay, missing things still say "Keep looking!" and offer the skip button.
        r = self.client.post(url, {"found": ["1"]})
        self.assertIn("missing=1", r["Location"])
        html = self.client.get(r["Location"]).content.decode()
        self.assertIn('name="skip"', html)
        self.assertEqual(html.count(" checked>"), 1)
        # A finished replay goes on to the next activity, and the item keeps its first done time.
        n = len(hunts[0].data["spots"])
        r = self.client.post(url, {"found": [str(i) for i in range(n)]})
        self.assertRedirects(r, reverse("activity", args=[second.id]), fetch_redirect_response=False)
        first.refresh_from_db()
        self.assertEqual(first.done_at, done_at)

    def test_embed_url_rejects_a_bad_point(self):
        from .streetview import embed_url

        with self.assertRaises(ValueError):
            embed_url({"lat": 135.0, "lng": 35.0})


class JapanContentTests(TestCase):
    """Slice 7: do and don't, safety, transport and buy in advance."""

    MODULES = ["dos_donts", "safety", "transport", "buy_in_advance"]

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("j@example.com", "j@example.com")

    def item(self, module, ages=(38, 4)):
        trip = Trip.objects.create(user=self.user, destination="japan")
        for a in ages:
            Traveller.objects.create(trip=trip, age=a)
        course = Course.objects.create(trip=trip)
        act = Activity.objects.filter(module__slug=module).first()
        return CourseItem.objects.create(course=course, order=0, activity=act)

    def page(self, item):
        self.client.force_login(self.user)
        r = self.client.get(reverse("activity", args=[item.id]), HTTP_USER_AGENT=PHONE)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_every_japan_module_is_ready(self):
        from content_admin.models import Module

        self.assertEqual(list(Module.objects.filter(country="japan", ready=False)), [])

    def test_each_new_module_page_renders(self):
        for slug in self.MODULES:
            with self.subTest(slug):
                html = self.page(self.item(slug))
                self.assertNotIn("coming soon", html)

    def test_safety_numbers_are_right(self):
        html = self.page(self.item("safety"))
        self.assertIn("call 110", html)
        self.assertIn("call 119", html)

    def test_buy_links_go_through_the_click_hook(self):
        item = self.item("buy_in_advance")
        html = self.page(item)
        self.assertIn(reverse("go", args=[item.id, "snack-box"]), html)
        self.assertNotIn("tokyotreat.com", html)
        r = self.client.get(reverse("go", args=[item.id, "snack-box"]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "https://www.tokyotreat.com/")
        click = ReferralClick.objects.get()
        self.assertEqual((click.link_id, click.trip_id), ("snack-box", item.course.trip_id))

    def test_go_is_not_an_open_redirect(self):
        item = self.item("buy_in_advance")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("go", args=[item.id, "nope"])).status_code, 404)
        other = get_user_model().objects.create_user("o@example.com", "o@example.com")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("go", args=[item.id, "snack-box"])).status_code, 404)
        self.assertEqual(ReferralClick.objects.count(), 0)

    def test_kids_chopsticks_only_with_a_child(self):
        self.assertIn("kids-chopsticks", self.page(self.item("buy_in_advance", ages=(38, 4))))
        self.assertNotIn("kids-chopsticks", self.page(self.item("buy_in_advance", ages=(40, 38))))

    def test_chopsticks_step_link_is_counted(self):
        item = chopsticks_item(self.user, [38, 4])
        self.client.force_login(self.user)
        r = self.client.get(reverse("go", args=[item.id, "kids-chopsticks"]))
        self.assertEqual(r.status_code, 302)
        self.assertRegex(r["Location"], r"^https://www\.aliexpress\.com/item/\d+\.html$")
        self.assertEqual(ReferralClick.objects.count(), 1)

    def test_kids_chopsticks_links_are_one_product(self):
        import yaml
        from django.conf import settings

        def walk(node):
            if isinstance(node, dict):
                if node.get("id") == "kids-chopsticks":
                    yield node["url"]
                for v in node.values():
                    yield from walk(v)
            elif isinstance(node, list):
                for v in node:
                    yield from walk(v)

        for name in ("chopsticks", "buy_in_advance"):
            data = yaml.safe_load((settings.BASE_DIR / "content" / "japan" / f"{name}.yaml").read_text())
            urls = list(walk(data))
            self.assertTrue(urls, name)
            for url in urls:
                self.assertRegex(url, r"^https://www\.aliexpress\.com/item/\d+\.html$")

    def test_aliexpress_links_are_products_not_searches(self):
        import yaml
        from django.conf import settings

        data = yaml.safe_load((settings.BASE_DIR / "content/japan/buy_in_advance.yaml").read_text())
        links = {l["id"]: l["url"] for l in data["activities"][0]["links"]}
        self.assertRegex(links["plug-adapter"], r"^https://www\.aliexpress\.com/item/\d+\.html$")
        for url in links.values():
            self.assertNotIn("/wholesale-", url)

    def test_safety_quiz_asks_for_the_number(self):
        from practice.items import add_items, question

        item = self.item("safety")
        add_items(item.course.trip, item.activity)
        q = question(item.course.trip, "safety/safety-intro/police")
        self.assertEqual(q["answer"], "110")
        self.assertIn("119", q["choices"])
        self.assertEqual(len(q["choices"]), 4)
