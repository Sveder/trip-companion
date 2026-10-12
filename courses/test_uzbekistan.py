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
# Japan files that carry reading_hebrew on every native word (T200; the rest follow in T201).
HEBREW_DONE = [Path(settings.BASE_DIR) / "content" / "japan" / "food.yaml"]


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

    def test_word_game_shows_the_uzbek_word_on_every_choice(self):
        # T180: the 'What do you say?' choices carry the word; Hebrew adds the way to say it.
        item = self.course.items.get(activity__slug="uz-words-lesson")
        for lang in ("en", "he"):
            html = self.client.get(reverse("activity", args=[item.id]) + f"?lang={lang}").content.decode()
            game = html.rsplit("lpage-pick", 1)[1].split("data-game-msg", 1)[0]
            choices = game.split('class="choice"')[1:]
            self.assertEqual(len(choices), 16, lang)
            for c in choices:
                self.assertIn('class="choice-word"', c, lang)
            self.assertIn(">Rahmat<", game)
            if lang == "en":
                self.assertNotIn("choice-say", game)  # the Latin word is not printed twice
            else:
                self.assertIn('<span class="choice-say">רחמת</span>', game)


class HebrewReadingTests(TestCase):
    """T197: a Hebrew page shows the Hebrew spelling next to the Latin word ('Osh · אוש'); an English page does not."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", "japan", "uzbekistan", verbosity=0)
        cls.user = get_user_model().objects.create_user("he@example.com", "he@example.com")
        uz = Trip.objects.create(user=cls.user, destination="uzbekistan")
        Traveller.objects.create(trip=uz, age=5)
        cls.uz = build_course(uz, list(Module.objects.filter(country="uzbekistan").values_list("id", flat=True)))
        other = get_user_model().objects.create_user("jp@example.com", "jp@example.com")
        jp = Trip.objects.create(user=other, destination="japan")
        Traveller.objects.create(trip=jp, age=5)
        cls.jp_user = other
        cls.jp = build_course(jp, list(Module.objects.filter(country="japan", slug="words").values_list("id", flat=True)))

    def test_every_uzbek_word_has_a_hebrew_spelling(self):
        def dicts(node):
            if isinstance(node, dict):
                yield node
                for v in node.values():
                    yield from dicts(v)
            elif isinstance(node, list):
                for v in node:
                    yield from dicts(v)

        missing = [f"{path.name}: {d['japanese']}" for path in [*sorted(CONTENT.glob("*.yaml")), *HEBREW_DONE]
                   for d in dicts(yaml.safe_load(path.read_text())) if d.get("japanese") and not d.get("reading_hebrew")]
        self.assertEqual(missing, [])

    def page(self, course, slug, lang):
        return self.client.get(reverse("activity", args=[course.items.get(activity__slug=slug).id]) + f"?lang={lang}").content.decode()

    def test_hebrew_word_line_and_no_hebrew_in_english(self):
        self.client.force_login(self.user)
        food = self.page(self.uz, "uz-food-lesson", "he")
        self.assertIn('Osh · <span class="he-say" lang="he">אוש</span>', food)
        words = self.page(self.uz, "uz-words-lesson", "he")
        self.assertIn('Rahmat · <span class="he-say" lang="he">רחמת</span>', words)
        for slug in ("uz-food-lesson", "uz-words-lesson", "uz-places-lesson"):
            self.assertNotIn("he-say", self.page(self.uz, slug, "en"), slug)

    def test_japan_words_cards_show_the_hebrew_spelling(self):
        self.client.force_login(self.jp_user)
        item = self.jp.items.filter(activity__type="words").first()
        url = reverse("activity", args=[item.id])
        he = self.client.get(url + "?lang=he").content.decode()
        self.assertIn('konnichiwa</h3>\n    <p class="he-say reading-he" lang="he">קוניצ\'יווה</p>', he.replace("&#x27;", "'"))
        self.assertNotIn("he-say", self.client.get(url + "?lang=en").content.decode())
