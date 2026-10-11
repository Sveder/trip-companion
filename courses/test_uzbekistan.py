"""Feedback T171 (Michael, 2026-10-11): Uzbekistan is a real choice with a short course of three modules."""
from pathlib import Path

import yaml
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from content_admin.loader import load_photo_credits
from content_admin.models import Activity, Module
from courses.builder import build_course
from trips.models import Traveller, Trip

CONTENT = Path(settings.BASE_DIR) / "content" / "uzbekistan"


class UzbekistanCourseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", "japan", "uzbekistan", verbosity=0)
        cls.user = get_user_model().objects.create_user("uz@example.com", "uz@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="uzbekistan")
        for age in (38, 4):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.course = build_course(cls.trip, list(Module.objects.filter(country="uzbekistan").values_list("id", flat=True)))

    def setUp(self):
        self.client.force_login(self.user)

    def test_three_ready_modules_of_3_to_5_pages(self):
        modules = Module.objects.filter(country="uzbekistan", ready=True)
        self.assertEqual(sorted(m.slug for m in modules), ["food", "places", "words"])
        for act in Activity.objects.filter(module__country="uzbekistan"):
            self.assertEqual(act.type, "lesson")
            self.assertTrue(3 <= len(act.data["pages"]) <= 5, act.slug)
        self.assertEqual(self.course.items.count(), 3)

    def test_trip_form_offers_uzbekistan_and_keeps_other_places_coming_soon(self):
        page = self.client.get(reverse("trip_setup"))
        self.assertContains(page, 'name="destination" value="uzbekistan"')
        self.assertNotContains(page, 'name="destination" value="georgia"')
        self.assertContains(page, "Coming soon")
        other = get_user_model().objects.create_user("uz2@example.com", "uz2@example.com")
        self.client.force_login(other)
        r = self.client.post(reverse("trip_setup"), {"destination": "uzbekistan", "grownup": 2, "kid": 1})
        self.assertRedirects(r, reverse("builder"))
        self.assertEqual(Trip.objects.get(user=other).destination, "uzbekistan")
        builder = self.client.get(reverse("builder"))
        self.assertContains(builder, "Uzbek words")
        self.assertNotContains(builder, "Japanese words")

    def test_every_word_has_sound_every_photo_has_credit_every_answer_is_a_choice(self):
        credits = load_photo_credits()
        for path in CONTENT.glob("*.yaml"):
            for act in yaml.safe_load(path.read_text())["activities"]:
                ids = {p["id"] for p in act["pictures"]}
                for pic in act["pictures"]:
                    self.assertTrue((Path(settings.BASE_DIR) / "static/img" / pic["img"]).exists(), pic["img"])
                for page in act["pages"]:
                    if page.get("reading"):
                        self.assertTrue((Path(settings.BASE_DIR) / f"static/audio/uzbekistan/{page['reading']}.mp3").exists(), page["reading"])
                    if page.get("photo_credit"):
                        self.assertIn(page["photo_credit"], credits)
                    self.assertTrue(page.get("title_he") and (page.get("text_he") or not page.get("text")), page["title"])
                    for rnd in page.get("rounds", []):
                        self.assertIn(rnd["answer"], rnd["choices"])
                        self.assertTrue(set(rnd["choices"]) <= ids)

    def test_course_names_uzbekistan_and_hides_the_japan_hunt(self):
        page = self.client.get(reverse("course") + "?lang=en")
        self.assertContains(page, "Our course for Uzbekistan")
        self.assertNotContains(page, "Our course for Japan")
        self.assertNotContains(page, "We are in Japan now")
        self.assertNotContains(page, ">In Japan<")
        he = self.client.get(reverse("course") + "?lang=he")
        self.assertContains(he, "המסלול שלנו לאוזבקיסטן")

    def test_words_lesson_speaks_uzbek(self):
        item = self.course.items.get(activity__slug="uz-words-lesson")
        page = self.client.get(reverse("activity", args=[item.id]) + "?lang=en")
        self.assertContains(page, "audio/uzbekistan/salom.mp3")
        self.assertContains(page, "audio/uzbekistan/rahmat.mp3")
        self.assertContains(page, "Yo&#x27;q")
        # The Latin word is not printed twice ('Salom <small>salom</small>').
        self.assertNotContains(page, "<small>salom</small>")
        he = self.client.get(reverse("activity", args=[item.id]) + "?lang=he")
        self.assertContains(he, "מדברים כמו ילדים באוזבקיסטן")
