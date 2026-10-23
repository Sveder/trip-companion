"""T304: 'People of Japan': real people and the Tokyo places they named in a public interview."""
from pathlib import Path

import yaml
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from content_admin.loader import load_photo_credits
from content_admin.models import Activity
from courses.builder import build_course
from trips.models import Traveller, Trip

CONTENT = Path(settings.BASE_DIR) / "content/japan/people.yaml"


class PeopleModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("pp@example.com", "pp@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (40, 5):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.acts = list(Activity.objects.filter(module__slug="people", module__country="japan").order_by("order"))
        course = build_course(cls.trip, [cls.acts[0].module_id])
        cls.items = {i.activity.slug: i for i in course.items.select_related("activity")}

    def test_three_people_each_a_lesson_with_4_to_6_spots_and_a_game(self):
        self.assertEqual([a.slug for a in self.acts], ["people-kondo", "people-beccat", "people-kato"])
        for act in self.acts:
            self.assertEqual(act.type, "lesson")
            pages = act.data["pages"]
            spots = [p for p in pages if p.get("quote") and p is not pages[0]]
            self.assertTrue(4 <= len(spots) <= 6, act.slug)
            self.assertEqual(pages[-1]["kind"], "pick", act.slug)
            for p in spots:
                self.assertTrue(any(t.startswith("Where:") for t in p["tips"]), p["title"])

    def test_every_page_names_and_links_its_source_and_quotes_are_short(self):
        credits = load_photo_credits()
        for act in self.acts:
            for p in act.data["pages"]:
                if p["kind"] == "pick":
                    continue  # the game asks about the pages before it
                self.assertTrue(p.get("source", "").startswith("https://guide.michelin.com/"), p["title"])
                self.assertTrue(p.get("source_name"), p["title"])
                if p.get("quote"):
                    self.assertTrue(p.get("quote_by") and p.get("quote_he"), p["title"])
                    self.assertLessEqual(p["quote"].count(". ") + 1, 2, p["title"])  # one or two sentences
                if p.get("img"):
                    self.assertIn(p["photo_credit"], credits)
                    self.assertTrue((Path(settings.BASE_DIR) / "static/img" / p["img"]).exists(), p["img"])

    def test_no_israel_or_hebrew_angle_in_the_english(self):
        doc = yaml.safe_load(CONTENT.read_text(encoding="utf-8"))

        def english(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if not str(k).endswith("_he"):
                        yield from english(v)
            elif isinstance(node, list):
                for v in node:
                    yield from english(v)
            elif isinstance(node, str):
                yield node

        text = " ".join(english(doc)).lower()
        for word in ("israel", "hebrew", "tel aviv"):
            self.assertNotIn(word, text)

    def test_page_shows_the_quote_and_the_source_link_in_en_and_he(self):
        self.client.force_login(self.user)
        item = self.items["people-kondo"]
        for lang, word, src in (("en", "Meet Marie Kondo", "From:"), ("he", "הכירו את מארי קונדו", "מקור:")):
            html = self.client.get(reverse("activity", args=[item.id]) + f"?lang={lang}").content.decode()
            self.assertIn(word, html)
            self.assertIn('class="pquote"', html)
            self.assertIn(src, html)
            self.assertIn('href="https://guide.michelin.com/vn/en/article/travel/my_tokyo_konmari"', html)
        html = self.client.get(reverse("activity", args=[item.id]) + "?lang=en").content.decode()
        self.assertIn("I especially like the fresh mint chocolate.", html)
        self.assertIn("— Marie Kondo", html)
