import re
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

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
        act = Activity.objects.get(module__slug="chopsticks", type="steps")
        self.assertTrue(act.module.ready)
        self.assertEqual([s["kind"] for s in act.data["steps"]], ["link", "text", "text", "record"])

    def test_chopsticks_has_no_video_and_keeps_the_written_how(self):
        # Michael, feedback T82: no video for chopsticks; the how-to lines, the practice and the record step stay.
        html = self.page(chopsticks_item(self.user, [38, 4]), HTTP_USER_AGENT=PHONE)
        self.assertNotIn("data-video-fallback", html)
        self.assertNotIn("comes soon", html)
        self.assertIn("How to hold them", html)
        self.assertIn("Move only the top stick", html)
        self.assertIn("Practise", html)
        self.assertIn("data-recorder", html)

    def test_referral_step_only_with_a_child(self):
        family = self.page(chopsticks_item(self.user, [38, 4]), HTTP_USER_AGENT=PHONE)
        self.assertIn("/kids-chopsticks/", family)
        adults = self.page(chopsticks_item(self.user, [40, 38]), HTTP_USER_AGENT=PHONE)
        self.assertNotIn("kids-chopsticks", adults)
        self.assertNotIn("kids' chopsticks", adults)

    def with_video(self, item, approved):
        # Chopsticks has no video now (T82); the steps page still supports one, so the tests add it.
        data = dict(item.activity.data)
        vid = {"kind": "video", "title": "Watch how", "youtube": "CBNw5yX1M34", "approved": approved,
               "fallback": ["Hold the top stick like a pencil."]}
        data["steps"] = data["steps"][:1] + [vid] + data["steps"][1:]
        item.activity.data = data
        item.activity.save()
        return item

    def test_unapproved_video_never_renders(self):
        item = self.with_video(chopsticks_item(self.user, [38, 4]), False)
        html = self.page(item, HTTP_USER_AGENT=PHONE)
        self.assertNotIn("CBNw5yX1M34", html)
        self.assertNotIn("youtube", html)
        self.assertIn("data-video-fallback", html)

    def test_approved_video_renders_from_nocookie(self):
        item = self.with_video(chopsticks_item(self.user, [38, 4]), True)
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
        acts = Activity.objects.filter(module__slug="streetview", type="streetview")
        self.assertTrue(acts[0].module.ready)
        self.assertGreaterEqual(acts.count(), 2)
        for act in acts:
            self.assertEqual(act.type, "streetview")
            self.assertGreaterEqual(len(act.data["spots"]), 3)

    def test_spots_are_japanese_things_not_random_passers_by(self):
        # Michael, feedback 2026-10-08: no "a woman with a pink hat who happened to be there".
        random = ("hat", "people", "cars", "pine tree", "green wall", "shop sign", '"no" sign')
        for act in Activity.objects.filter(module__slug="streetview", type="streetview"):
            for spot in act.data["spots"]:
                for word in random:
                    self.assertNotIn(word, spot["text"].lower(), (act.slug, spot["text"]))
        cats = Activity.objects.get(module__slug="streetview", slug="streetview-intro")
        self.assertIn("lucky cat", cats.data["intro"])

    def test_every_spot_has_a_proper_name_and_why_it_matters(self):
        # Michael, feedback 2026-10-08: "a big orange gate" is a torii gate; say why each thing is interesting.
        for act in Activity.objects.filter(module__slug="streetview", type="streetview"):
            for spot in act.data["spots"]:
                self.assertTrue(spot.get("name"), (act.slug, spot["text"]))
                self.assertGreaterEqual(len(spot.get("about", "")), 40, (act.slug, spot["name"]))
        inari = Activity.objects.get(module__slug="streetview", slug="streetview-inari")
        self.assertIn("Torii gate", [s["name"] for s in inari.data["spots"]])
        html = self.client.get(reverse("activity", args=[self.item("streetview-inari").id])).content.decode()
        self.assertIn('<span class="spot-name">Torii gate</span>', html)
        self.assertIn("the home of a kami", html)

    def test_cat_temple_icons_are_drawn_files_not_new_emoji(self):
        # T272, Michael 2026-10-13: koshi, kawara and sekihi showed a plain white square (Unicode 13 emoji).
        cats = Activity.objects.get(module__slug="streetview", slug="streetview-intro")
        html = self.client.get(reverse("activity", args=[self.item().id])).content.decode()
        for spot in cats.data["spots"]:
            self.assertTrue(spot.get("icon"), spot["name"])
            path = Path(settings.BASE_DIR) / "static" / "img" / "hunt" / f"{spot['icon']}.svg"
            self.assertTrue(path.exists(), path)
            self.assertNotIn("<text", path.read_text(), path)
            self.assertIn(f"img/hunt/{spot['icon']}", html)
        self.assertNotIn('class="spot-emoji"', html)

    def test_no_content_emoji_is_too_new_for_old_phones_and_tvs(self):
        # T272: an emoji from Unicode 12 or later draws as a blank square on older Android phones and TVs.
        new = re.compile("[\U0001FA70-\U0001FAFF\U0001F6D5-\U0001F6DF\U0001F6FB-\U0001F6FF\U0001F90C-\U0001F90F"
                         "\U0001F972\U0001F977-\U0001F97A\U0001F9A3-\U0001F9AF\U0001F9CB-\U0001F9CF]")
        files = list((Path(settings.BASE_DIR) / "content").rglob("*.yaml")) + [Path(settings.BASE_DIR) / "there" / "things.py"]
        for f in files:
            for n, line in enumerate(f.read_text().splitlines(), 1):
                self.assertIsNone(new.search(line), f"{f.name}:{n}: {line.strip()}")

    def test_the_big_view_link_says_full_screen(self):
        html = self.client.get(reverse("activity", args=[self.item().id])).content.decode()
        self.assertIn('rel="noopener">Full screen</a>', html)
        self.assertNotIn("Open it big", html)

    def test_page_shows_the_embed_and_the_spot_list(self):
        item = self.item()
        r = self.client.get(reverse("activity", args=[item.id]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("https://www.google.com/maps/embed?pb=!6m7!1m6!2m2!1d35.6486000!2d139.6468000!3f120!4f0!5f1", html)
        self.assertNotIn("key=", html)
        self.assertEqual(html.count('name="found"'), 5)
        self.assertIn("A lucky cat with one paw up", html)

    def test_hunt_list_and_lesson_picture_use_different_classes(self):
        # T73: the lesson picture box once reused .spots/.spot, and its absolute
        # positioning collapsed every row of the hunt list to height 0.
        hunt = self.client.get(reverse("activity", args=[self.item().id])).content.decode()
        self.assertIn('<ul class="spots">', hunt)
        self.assertIn('class="spot"', hunt)
        self.assertNotIn("lspot", hunt)
        lesson_act = Activity.objects.get(module__slug="food", slug="sushi-lesson")
        course = Course.objects.create(trip=Trip.objects.create(user=self.user, destination="japan"))
        lesson = CourseItem.objects.create(course=course, order=0, activity=lesson_act)
        html = self.client.get(reverse("activity", args=[lesson.id])).content.decode()
        self.assertIn('class="lspots" data-spots', html)
        self.assertIn('class="lspot"', html)
        self.assertNotIn('class="spots"', html)
        self.assertNotIn('class="spot"', html)
        css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text()
        self.assertEqual(len(re.findall(r"^\.spots \{", css, re.M)), 1)
        self.assertEqual(len(re.findall(r"^\.spot \{", css, re.M)), 1)

    def test_desktop_panorama_sticks_beside_the_spot_list(self):
        # T212: the panorama and its help line sit in one column that stays in view on a desktop.
        html = self.client.get(reverse("activity", args=[self.item().id])).content.decode()
        self.assertRegex(html, r'<div class="sv-col">\s*<div class="sv-frame">')
        self.assertLess(html.index('sv-help"'), html.index('class="spot-form"'))
        css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text()
        self.assertIn(".hunt .sv-col { position: sticky; top: 1rem; }", css)
        self.assertIn(".hunt .sv-frame { height: min(70vh, 640px); }", css)

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
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertIsNotNone(item.done_at)

    def test_found_things_render_folded_and_the_list_is_compact(self):
        # T273 (Michael): a found thing folds to its title; a tap opens it again (hunt.js).
        item = self.item()
        html = self.client.get(self.done(item, ["0", "2"])["Location"]).content.decode()
        self.assertEqual(html.count('class="spot done"'), 2)
        self.assertEqual(html.count('class="spot"'), 3)
        css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text()
        self.assertIn(".spot.done:not(.open) .spot-about", css)
        self.assertIn("padding: .35rem .6rem", css)
        js = (Path(settings.BASE_DIR) / "static" / "js" / "hunt.js").read_text()
        self.assertIn("' open'", js)

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
        hunts = list(Activity.objects.filter(module__slug="streetview", type="streetview")[:2])
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
        home = self.client.get(reverse("next_step"))
        self.assertRedirects(home, reverse("activity", args=[second.id]), fetch_redirect_response=False)

    def test_praise_after_a_skip_with_nothing_found_says_good_try(self):
        trip = Trip.objects.create(user=self.user, destination="japan")
        Traveller.objects.create(trip=trip, age=4)
        course = Course.objects.create(trip=trip)
        hunts = list(Activity.objects.filter(module__slug="streetview", type="streetview")[:2])
        first = CourseItem.objects.create(course=course, order=0, activity=hunts[0])
        CourseItem.objects.create(course=course, order=1, activity=hunts[1])
        r = self.client.post(reverse("activity_done", args=[first.id]), {"found": [], "skip": "1"})
        n = len(hunts[0].data["spots"])
        self.assertEqual(r["Location"], reverse("activity_praise", args=[first.id]) + f"?found=0&of={n}")
        html = self.client.get(r["Location"]).content.decode()
        self.assertNotIn("You found 0", html)
        self.assertNotIn("Great job!", html)
        self.assertIn("Good try!", html)
        self.assertIn("You can play it again from Our adventure.", html)
        html = self.client.get(reverse("activity_praise", args=[first.id]) + f"?found=2&of={n}").content.decode()
        self.assertIn(f"You found 2 of {n}!", html)
        self.assertIn("Great job!", html)

    def test_stars_and_chime_only_when_the_module_is_finished(self):
        # Feedback T83 (our 4-year-old): finishing a module brings a star explosion and a chime.
        trip = Trip.objects.create(user=self.user, destination="japan")
        Traveller.objects.create(trip=trip, age=6)
        course = Course.objects.create(trip=trip)
        hunts = list(Activity.objects.filter(module__slug="streetview", type="streetview")[:2])
        other = Activity.objects.exclude(module__slug="streetview").filter(type="steps").first()
        first = CourseItem.objects.create(course=course, order=0, activity=hunts[0])
        second = CourseItem.objects.create(course=course, order=1, activity=hunts[1])
        CourseItem.objects.create(course=course, order=2, activity=other)
        first.mark_done()
        html = self.client.get(reverse("activity_praise", args=[first.id])).content.decode()
        self.assertNotIn("data-celebrate", html)
        self.assertNotIn("You finished", html)
        second.mark_done()
        html = self.client.get(reverse("activity_praise", args=[second.id])).content.decode()
        self.assertRegex(html, r"<body [^>]*data-celebrate>")
        self.assertIn("You finished", html)

    def test_a_done_hunt_opens_with_no_ticks_and_plays_again(self):
        trip = Trip.objects.create(user=self.user, destination="japan")
        Traveller.objects.create(trip=trip, age=4)
        course = Course.objects.create(trip=trip)
        hunts = list(Activity.objects.filter(module__slug="streetview", type="streetview")[:2])
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

    def test_skip_with_nothing_found_offers_play_again_on_the_course(self):
        # T42: a hunt skipped with 0 found shows "found 0 of N" and a Play again link; highlights leave it out.
        trip = Trip.objects.create(user=self.user, destination="japan")
        Traveller.objects.create(trip=trip, age=4)
        course = Course.objects.create(trip=trip)
        hunts = list(Activity.objects.filter(module__slug="streetview", type="streetview")[:3])
        first = CourseItem.objects.create(course=course, order=0, activity=hunts[0])
        second = CourseItem.objects.create(course=course, order=1, activity=hunts[1])
        CourseItem.objects.create(course=course, order=2, activity=hunts[2])
        n0, n1 = len(hunts[0].data["spots"]), len(hunts[1].data["spots"])
        self.client.post(reverse("activity_done", args=[first.id]), {"found": [], "skip": "1"})
        self.client.post(reverse("activity_done", args=[second.id]), {"found": ["0", "1"], "skip": "1"})
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.found, second.found), (0, 2))
        html = self.client.get(reverse("course")).content.decode()
        self.assertIn(f"found 0 of {n0}", html)
        self.assertIn(f"found 2 of {n1}", html)
        again = reverse("activity", args=[first.id]) + "?again=1"
        self.assertIn(f'href="{again}"', html)
        self.assertEqual(html.count("Play again"), 1)
        replay = self.client.get(again).content.decode()
        self.assertEqual(replay.count(" checked>"), 0)
        # The highlights list the hunt with 2 found, not the one with 0.
        html = self.client.get(reverse("highlights")).content.decode()
        self.assertNotIn(f'href="{reverse("activity", args=[first.id])}"', html)
        self.assertIn(f'href="{reverse("activity", args=[second.id])}"', html)
        # A better replay raises the count, a weaker one keeps the best; the link goes away above 0.
        self.client.post(reverse("activity_done", args=[first.id]), {"found": [str(i) for i in range(n0)]})
        self.client.post(reverse("activity_done", args=[first.id]), {"found": [], "skip": "1"})
        first.refresh_from_db()
        self.assertEqual(first.found, n0)
        html = self.client.get(reverse("course")).content.decode()
        self.assertNotIn("Play again", html)
        self.assertIn(f"found {n0} of {n0}", html)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "he"
        CourseItem.objects.filter(id=first.id).update(found=0)
        html = self.client.get(reverse("course")).content.decode()
        self.assertIn(f"מצאנו 0 מתוך {n0}", html)
        self.assertIn("לשחק שוב", html)
        html = self.client.get(reverse("activity_praise", args=[first.id]) + f"?found=0&of={n0}").content.decode()
        self.assertIn("אפשר לשחק בו שוב מתוך ההרפתקה שלנו.", html)

    def test_a_course_rebuild_keeps_the_found_count(self):
        from courses.builder import build_course

        item = self.item()
        item.mark_done()
        CourseItem.objects.filter(id=item.id).update(found=0)
        build_course(item.course.trip, [item.activity.module_id])
        again = CourseItem.objects.get(course=item.course, activity=item.activity)
        self.assertEqual(again.found, 0)
        self.assertIsNotNone(again.done_at)

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
        # The slice 7 items, not the lessons (activities/test_lesson.py covers those).
        act = Activity.objects.filter(module__slug=module).exclude(type="lesson").first()
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
        intro = next(a for a in data["activities"] if a["id"] == "buy_in_advance-intro")
        links = {l["id"]: l["url"] for l in intro["links"]}
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


class LookTests(TestCase):
    """Feedback T83 (our 4-year-old and Michael): flag red as a highlight only, a Nara deer guide, stars on a finish, a rare penguin."""

    def test_the_theme_and_the_guide(self):
        html = self.client.get(reverse("privacy")).content.decode()
        self.assertIn('<meta name="theme-color" content="#ffffff">', html)  # no red browser bar
        self.assertNotIn("var(--guide-antler)", html)  # T87: no deer on an app-wide page
        self.assertIn('class="guide mark small"', html)  # the neutral mark in the header
        self.assertRegex(html, r'<template id="penguin-egg">\s*<svg class="penguin"')
        self.assertNotIn("fox", html)
        css = (settings.BASE_DIR / "static/css/app.css").read_text()
        self.assertIn("--c-primary: #bc002d;", css)
        self.assertNotIn("confetti", css)

    def test_the_deer_is_on_japan_screens_only(self):
        """Feedback T87 (Michael): the Nara deer belongs to Japan. App-wide screens get the neutral mark."""
        deer = "var(--guide-antler)"
        for name in ("home", "signin", "privacy"):  # signed out: welcome, sign-in, a site page
            html = self.client.get(reverse(name)).content.decode()
            self.assertNotIn(deer, html, name)
        self.assertNotIn(deer, self.client.get("/no-such-page/").content.decode())
        user = get_user_model().objects.create_user("deer@example.com", "deer@example.com")
        self.client.force_login(user)
        self.assertNotIn(deer, self.client.get(reverse("trip_setup")).content.decode())  # no trip yet
        call_command("load_content", verbosity=0)
        item = chopsticks_item(user, [5])
        self.assertNotIn(deer, self.client.get(reverse("trip_setup")).content.decode())  # app-wide, also with a Japan trip
        for url in (reverse("course"), reverse("activity", args=[item.id]), reverse("there"), reverse("quiz")):
            html = self.client.get(url, follow=True).content.decode()
            self.assertIn(deer, html, url)
        # A country with no guide yet: its screens show no deer.
        Trip.objects.filter(user=user).update(destination="italy")
        self.assertNotIn(deer, self.client.get(reverse("course")).content.decode())

    def test_the_icons_show_the_mark_not_the_deer(self):
        """T89: the favicon and the share image are app-wide, so they show the paper plane (T87), not the deer."""
        svg = (settings.BASE_DIR / "static/img/favicon.svg").read_text()
        self.assertNotIn("#b5713c", svg)  # the deer's fur colour
        self.assertIn("M22 62 L98 26 L72 98 L58 70 Z", svg)  # the plane path from includes/mark.html
        html = self.client.get(reverse("privacy")).content.decode()
        self.assertIn('content="Trip Companion: a paper plane over a sun and the words Get ready for Japan"', html)
        self.assertNotIn("deer", html)

    def test_the_celebration_script(self):
        js = (settings.BASE_DIR / "static/js/celebrate.js").read_text()
        self.assertIn("function stars()", js)
        self.assertIn("function chime()", js)
        self.assertIn("Math.random() >= 1 / 6", js)  # the penguin comes in about one party out of six
        self.assertNotIn("confetti", js)



class SpotRingSpacingTests(TestCase):
    """T99: since T103 the numbers sit beside the picture and a small hollow ring marks each thing.
    On a 412 px phone a 400x260 picture is about 332x216 px, and a ring with its shadow is about 20 px.
    Two rings on the same picture must not touch, or a child cannot tell which line goes where."""

    def test_no_two_rings_touch(self):
        import math

        import yaml

        touching = []

        def walk(node, path):
            if isinstance(node, dict):
                spots = node.get("spots") if node.get("kind") == "spots" else None
                for i, a in enumerate(spots or []):
                    for b in spots[i + 1:]:
                        if math.hypot((a["x"] - b["x"]) * 3.32, (a["y"] - b["y"]) * 2.16) < 22:
                            touching.append(f"{path} {node.get('title')}: {a['label']} / {b['label']}")
                for v in node.values():
                    walk(v, path)
            elif isinstance(node, list):
                for v in node:
                    walk(v, path)

        for f in sorted((settings.BASE_DIR / "content/japan").glob("*.yaml")):
            walk(yaml.safe_load(f.read_text()), f.name)
        self.assertEqual(touching, [])


class LessonIntroTests(TestCase):
    """T100: the lesson intro line shows on page 1 only, not above every page."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("i@example.com", "i@example.com")

    def test_intro_sits_in_page_one_only_en_and_he(self):
        self.client.force_login(self.user)
        course = Course.objects.create(trip=Trip.objects.create(user=self.user, destination="japan"))
        lessons = [a for a in Activity.objects.all() if a.data.get("pages") and a.data.get("intro")]
        self.assertGreaterEqual(len(lessons), 8)
        for n, act in enumerate(lessons):
            item = CourseItem.objects.create(course=course, order=n, activity=act)
            for lang, key in (("en", "intro"), ("he", "intro_he")):
                html = self.client.get(reverse("activity", args=[item.id]) + "?lang=" + lang).content.decode()
                intro = str(escape(act.data.get(key) or act.data["intro"]))
                self.assertEqual(html.count(intro), 1, (act.slug, lang))
                pages = html.split("data-page ")[1:]
                self.assertIn(intro, pages[0], (act.slug, lang))
                self.assertEqual(html.count('class="lead'), 1, (act.slug, lang))


class PhoneSpotsTests(TestCase):
    """T116 (feedback #7): on a phone the tap-the-dots picture gets most of the card, and the numbers still sit beside it."""

    def test_phone_rule_and_number_offset(self):
        css = (settings.BASE_DIR / "static/css/app.css").read_text()
        rule = re.search(r"/\* T116.*?@media \(max-width: 600px\) \{(.*?)\n\}", css, re.S).group(1)
        self.assertIn(".lspots.edge { padding: 14px 24px; margin: 0 -14px; }", rule)
        self.assertIn(".lspot { width: 20px; height: 20px;", rule)
        self.assertIn(".spot-info { font-size: 1rem; padding: .4rem .8rem; }", rule)
        # A 20 px number sits 13 px outside the picture (inside the 24 px band); a 34 px desktop number 20 px.
        js = (settings.BASE_DIR / "static/js/lesson.js").read_text()
        self.assertIn("var off = s.b.offsetWidth / 2 + 3,", js)

    def test_tv_number_beside_the_picture(self):
        # T172: a 42 px TV number sits 24 px outside the picture, so even at the pulse peak (scale 1.15) it stays off
        # the picture and inside the 48 px TV band. The old 20 px cap put it 1-4 px over the picture edge.
        css = (settings.BASE_DIR / "static/css/app.css").read_text()
        size = int(re.search(r"\.tv \.lspot \{ width: (\d+)px;", css).group(1))
        band = int(re.search(r"\.tv \.lspots\.edge \{ padding: \d+px (\d+)px; \}", css).group(1))
        scale = float(re.search(r"@keyframes pulse \{ 50% \{ transform: translate\(-50%, -50%\) scale\(([\d.]+)\)", css).group(1))
        off = size / 2 + 3
        self.assertLess(size / 2 * scale, off + 0.5)
        self.assertLessEqual(off + size / 2 * scale, band + 0.5)


class TvFlipCardTests(TestCase):
    """T138: on the TV the flip cards are wide with a big picture, and the name sits right under the picture.
    The browser check is trip-companion-tools/t138_tv_flip_probe.cjs (name tops in a row within 4 px, picture 45 percent of the front)."""

    def test_tv_flip_rules(self):
        css = (settings.BASE_DIR / "static/css/app.css").read_text()
        self.assertIn(".tv .flips { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));", css)
        self.assertIn(".tv .flip img, .tv .flip img.flip-photo { height: 260px; }", css)
        self.assertIn(".tv .flip-front { justify-content: flex-start; }", css)
        # Phone and desktop keep the T118 rules.
        self.assertIn(".flip-front { align-self: stretch; justify-content: space-between; }", css)
        self.assertIn(".flip img, .flip img.flip-photo { height: 72px; }", css)


class FlipRowTests(TestCase):
    """T213: on a tablet or a desktop the flip cards wrap in a centred flex row, so a short last row sits in the centre.
    The phone and the TV keep a grid. The browser check is trip-companion-tools/dev_69aa1f_fliprow.cjs (gaps within 8 px)."""

    def test_flip_row_rules(self):
        css = (settings.BASE_DIR / "static/css/app.css").read_text()
        self.assertIn(".flips { display: flex; flex-wrap: wrap; justify-content: center;", css)
        self.assertIn(".flips > .flip { flex: 0 1 200px; min-width: 0; }", css)
        phone = css[css.index("@media (max-width: 600px) {\n  .flips"):]
        self.assertIn(".flips { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));", phone[:200])

class TabletSpotsTests(TestCase):
    """T141: on a tablet or a desktop the tap-the-dots picture grows past 420 px; the TV and the phone keep their own rules."""

    def test_tablet_rule(self):
        css = (settings.BASE_DIR / "static/css/app.css").read_text()
        rule = re.search(r"/\* T141.*?@media \(min-width: 601px\) \{(.*?)\n\}", css, re.S).group(1)
        self.assertIn("html:not(.tv) .lspots.edge { max-width: 760px; }", rule)
        self.assertIn("html:not(.tv) .lspots .lpic { max-width: none; }", rule)
        # The base rules stay for the TV and for a page with no JavaScript.
        self.assertIn(".lspots.edge { max-width: 500px; padding: 18px 40px; }", css)
