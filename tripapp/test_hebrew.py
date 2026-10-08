"""Hebrew (feedback T49): the language switch, right-to-left pages, and Hebrew content and quizzes."""
from pathlib import Path

import polib
import yaml
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from content_admin.i18n import localize
from content_admin.models import Activity, Module
from courses.builder import build_course
from practice.items import add_items, question
from trips.models import Traveller, Trip

CONTENT = Path(settings.BASE_DIR) / "content" / "japan"
# Modules a child sees. Every text in them must have Hebrew.
KIDS_MODULES = ("food", "words", "dos_donts", "safety", "chopsticks", "streetview")
TEXT_KEYS = ("title", "summary", "intro", "text", "name", "about", "place", "meaning", "question", "label", "tips", "fallback")


class LocalizeTests(TestCase):
    def test_hebrew_value_replaces_english_and_he_keys_go_away(self):
        data = {"title": "Bow", "title_he": "קידה", "cards": [{"text": "Hi", "text_he": "היי", "emoji": "🙇"}, {"text": "Only English"}]}
        self.assertEqual(localize(data, hebrew=True), {"title": "קידה", "cards": [{"text": "היי", "emoji": "🙇"}, {"text": "Only English"}]})
        self.assertEqual(localize(data, hebrew=False), {"title": "Bow", "cards": [{"text": "Hi", "emoji": "🙇"}, {"text": "Only English"}]})


class SwitchTests(TestCase):
    def test_english_by_default_even_for_a_hebrew_browser(self):
        html = self.client.get("/", HTTP_ACCEPT_LANGUAGE="he").content.decode()
        self.assertIn('<html lang="en" dir="ltr"', html)
        self.assertIn("Get ready for your trip!", html)
        self.assertIn('value="he"', html)  # the switch offers Hebrew

    def test_switch_posts_and_the_cookie_keeps_hebrew(self):
        r = self.client.post(reverse("set_language"), {"language": "he", "next": "/"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        html = self.client.get("/").content.decode()
        self.assertIn('<html lang="he" dir="rtl"', html)
        self.assertIn("מתכוננים לטיול!", html)
        self.assertIn('value="en"', html)  # and now offers English
        self.client.post(reverse("set_language"), {"language": "en", "next": "/"})
        self.assertIn('dir="ltr"', self.client.get("/").content.decode())

    def test_lang_in_the_url_sets_the_language(self):
        self.assertIn('dir="rtl"', self.client.get("/?lang=he").content.decode())
        self.assertIn('dir="rtl"', self.client.get("/").content.decode())
        self.assertIn('dir="ltr"', self.client.get("/?lang=en").content.decode())
        self.assertIn('dir="ltr"', self.client.get("/?lang=xx").content.decode())


class HebrewContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        user = get_user_model().objects.create_user("he@example.com", "he@example.com")
        cls.user = user
        cls.trip = Trip.objects.create(user=user, destination="japan")
        for age in (40, 4):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.course = build_course(cls.trip, list(Module.objects.values_list("id", flat=True)))

    def setUp(self):
        self.client.force_login(self.user)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "he"

    def item(self, slug):
        return self.course.items.get(activity__slug=slug)

    def test_words_page_is_hebrew(self):
        html = self.client.get(reverse("activity", args=[self.item("words-intro").id])).content.decode()
        for text in ("בואו נגיד את זה ביפנית!", "שלום", "תודה", "לחצו כדי לשמוע", "עשינו את זה!"):
            self.assertIn(text, html)
        self.assertIn("こんにちは", html)  # the Japanese stays
        self.assertNotIn(">hello<", html)

    def test_food_cards_streetview_and_chopsticks_are_hebrew(self):
        pages = {"food-cards": ["סושי", "אוניגירי"], "streetview-intro": ["מנקי-נקו", "מה צריך למצוא", "מצאנו את כולם!"],
                 "chopsticks-intro": ["מזיזים רק את המקל העליון", "הפעלת המצלמה"], "safety-intro": ["110", "קובאן"]}
        for slug, texts in pages.items():
            html = self.client.get(reverse("activity", args=[self.item(slug).id])).content.decode()
            for text in texts:
                self.assertIn(text, html, slug)

    def test_course_and_builder_use_hebrew_titles(self):
        self.assertIn("אוכל יפני", self.client.get(reverse("course")).content.decode())
        self.assertIn("אומרים שלום ותודה ביפנית.", self.client.get(reverse("builder")).content.decode())

    def test_quiz_asks_and_checks_in_hebrew(self):
        words = Activity.objects.get(slug="words-intro")
        add_items(self.trip, words)
        with translation.override("he"):
            q = question(self.trip, "words/words-intro/arigatou")
        self.assertEqual(q["prompt"], "מה פירוש המילה הזאת?")
        self.assertEqual(q["answer"], "תודה")
        self.assertTrue(all(any("֐" <= ch <= "׿" for ch in c) for c in q["choices"]))
        html = self.client.get(reverse("quiz")).content.decode()
        self.assertIn("זמן חידון", html)
        # Answer the first question with its right Hebrew answer: the quiz says yes.
        key = self.client.session["quiz"]["keys"][0]
        with translation.override("he"):
            right = question(self.trip, key)["answer"]
        html = self.client.post(reverse("quiz"), {"key": key, "choice": right}).content.decode()
        self.assertIn("כן! כל הכבוד!", html)

    def test_hebrew_safety_quiz_keeps_the_numbers(self):
        add_items(self.trip, Activity.objects.get(slug="safety-intro"))
        with translation.override("he"):
            q = question(self.trip, "safety/safety-intro/police")
        self.assertEqual(q["answer"], "110")
        self.assertEqual(q["prompt"], "לאיזה מספר מתקשרים למשטרה ביפן?")


class CoverageTests(TestCase):
    def test_every_kids_text_has_hebrew(self):
        missing = []

        def walk(node, where):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in TEXT_KEYS and f"{key}_he" not in node:
                        missing.append(f"{where}: {key}")
                    walk(value, where)
            elif isinstance(node, list):
                for v in node:
                    walk(v, where)

        for slug in KIDS_MODULES:
            walk(yaml.safe_load((CONTENT / f"{slug}.yaml").read_text(encoding="utf-8")), slug)
        self.assertEqual(missing, [])

    def test_every_interface_string_has_hebrew(self):
        po = polib.pofile(str(Path(settings.BASE_DIR) / "locale/he/LC_MESSAGES/django.po"))
        self.assertEqual([e.msgid for e in po if not (e.msgstr or all(e.msgstr_plural.values() or [""])) and not e.obsolete], [])
        self.assertTrue((Path(settings.BASE_DIR) / "locale/he/LC_MESSAGES/django.mo").exists())
