"""Lessons (feedback T51): a course of 10-20 short pages with pictures, games and a video slot."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from content_admin.models import Activity
from courses.builder import build_course
from courses.models import CourseItem
from trips.models import Traveller, Trip

from .lesson import KINDS, visible_pages


class SushiLessonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("l@example.com", "l@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (38, 4):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.act = Activity.objects.get(module__slug="food", slug="sushi-lesson")
        course = build_course(cls.trip, [cls.act.module_id])
        cls.item = course.items.get(activity=cls.act)

    def page(self, lang="en"):
        self.client.force_login(self.user)
        r = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}")
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_lesson_has_10_to_20_pages_and_every_kind(self):
        pages = self.act.data["pages"]
        self.assertTrue(10 <= len(pages) <= 20, len(pages))
        self.assertEqual({p["kind"] for p in pages}, set(KINDS))
        kinds = [p["kind"] for p in pages]
        # The video sits in the middle, not first or last.
        self.assertTrue(len(pages) // 4 <= kinds.index("video") <= 3 * len(pages) // 4)

    def test_every_picture_exists_and_every_game_answer_is_a_choice(self):
        data = self.act.data
        static = Path(settings.BASE_DIR) / "static" / "img"
        pics = {p["id"] for p in data["pictures"]}
        imgs = [p["img"] for p in data["pictures"]] + [p["img"] for p in data["pages"] if p.get("img")]
        imgs += [c["img"] for p in data["pages"] for c in p.get("cards", [])]
        for img in imgs:
            self.assertTrue((static / img).exists(), img)
        for p in data["pages"]:
            if p["kind"] == "pick":
                for r in p["rounds"]:
                    self.assertIn(r["answer"], r["choices"])
                    self.assertTrue(set(r["choices"]) <= pics)
            if p["kind"] == "train":
                for r in p["rounds"]:
                    self.assertIn(r["answer"], p["belt"])

    def test_page_renders_every_kind_in_english(self):
        html = self.page()
        self.assertEqual(html.count("data-page "), len(self.act.data["pages"]))
        for kind in KINDS:
            self.assertIn(f"lpage-{kind}", html)
        self.assertIn("Tap the plate", html)
        self.assertIn('data-spot="7"', html)            # 8 dots on the plate
        self.assertIn("data-right", html)                # the pick game marks the right picture
        self.assertIn('data-plate="sake"', html)         # the sushi train
        self.assertIn("Sushiro", html)                   # where to eat it in Japan
        self.assertIn("Page 1 of 13", html)
        self.assertIn("js/lesson.js", html)

    def test_page_is_hebrew_in_hebrew(self):
        html = self.page("he")
        self.assertIn("הכל על סושי", html)
        self.assertIn("געו בצלחת", html)
        self.assertIn("תפסו את הסלמון!", html)
        self.assertIn("דף 1 מתוך 13", html)
        self.assertNotIn("Tap the plate", html)

    def test_unapproved_video_shows_the_written_lines_and_no_id(self):
        html = self.page()
        self.assertNotIn("R7zkF_wpmLI", html)
        self.assertNotIn("comes soon", html)
        self.assertIn("How to make a roll", html)
        self.assertIn("bamboo mat", html)

    def test_approved_video_renders(self):
        data = dict(self.act.data)
        data["pages"] = [dict(p, approved=True) if p["kind"] == "video" else p for p in data["pages"]]
        pages = visible_pages(data, self.trip)
        video = next(p for p in pages if p["kind"] == "video")
        self.assertTrue(video["show_video"])
        self.assertEqual(video["youtube"], "R7zkF_wpmLI")

    def test_done_marks_the_lesson_done(self):
        self.client.force_login(self.user)
        self.client.post(reverse("activity_done", args=[self.item.id]))
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.done_at)


class NewActivityJoinsBuiltCourses(TestCase):
    def test_load_content_adds_a_new_activity_and_keeps_done_marks(self):
        call_command("load_content", verbosity=0)
        user = get_user_model().objects.create_user("n@example.com", "n@example.com")
        trip = Trip.objects.create(user=user, destination="japan")
        Traveller.objects.create(trip=trip, age=40)
        food = Activity.objects.get(slug="food-cards").module
        course = build_course(trip, [food.id])
        # A course built before the lesson existed: only the cards, done.
        course.items.exclude(activity__slug="food-cards").delete()
        course.items.update(done_at="2026-10-01T10:00Z")
        call_command("load_content", verbosity=0)
        slugs = list(CourseItem.objects.filter(course=course).values_list("activity__slug", "done_at"))
        self.assertEqual([s for s, _ in slugs], ["food-cards", "sushi-lesson"])
        self.assertIsNotNone(slugs[0][1])
        self.assertIsNone(slugs[1][1])
