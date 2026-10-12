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

    def test_ready_modules_of_3_to_5_pages(self):
        # T234 added 'At the bazaar' (bazaar.yaml) and 'Silk Road crafts and blue tiles' (crafts.yaml) to the first three.
        modules = Module.objects.filter(country="uzbekistan", ready=True)
        self.assertEqual(sorted(m.slug for m in modules), ["bazaar", "crafts", "food", "places", "words"])
        for act in Activity.objects.filter(module__country="uzbekistan"):
            self.assertEqual(act.type, "lesson")
            self.assertTrue(3 <= len(act.data["pages"]) <= 5, act.slug)
        self.assertEqual(self.course.items.count(), 5)

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
                    for word in [page, *page.get("cards", [])]:
                        if word.get("reading"):
                            self.assertTrue((Path(settings.BASE_DIR) / f"static/audio/uzbekistan/{word['reading']}.mp3").exists(), word["reading"])
                        if word.get("img"):
                            self.assertTrue((Path(settings.BASE_DIR) / "static/img" / word["img"]).exists(), word["img"])
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


    def test_bazaar_lesson_counts_to_five_and_picks_the_fruit(self):
        # T234 (Michael, 2026-10-12): 'At the bazaar', Chorsu, fruit, spices, count 1-5 with sound, a pick-the-fruit game.
        item = self.course.items.get(activity__slug="uz-bazaar-lesson")
        url = reverse("activity", args=[item.id])
        en = self.client.get(url + "?lang=en")
        self.assertContains(en, "A trip to the bazaar")
        self.assertContains(en, "img/photo/uzbekistan/uz-chorsu.jpg")
        for word in ("bir", "ikki", "uch", "tort", "besh", "olma", "anor", "uzum", "qovun", "zira", "chorsu"):
            self.assertContains(en, f"audio/uzbekistan/{word}.mp3")
        self.assertContains(en, "To&#x27;rt")
        game = en.content.decode().rsplit("lpage-pick", 1)[1].split("data-game-msg", 1)[0]
        self.assertEqual(game.count('class="choice"'), 16)
        he = self.client.get(url + "?lang=he")
        self.assertContains(he, "טיול לשוק")
        self.assertContains(he, 'Chorsu</span><span class="say-sub"><span class="he-say" lang="he">צ\'ורסו</span>'.replace("'", "&#x27;"))
        credits = self.client.get(reverse("credits"))
        self.assertContains(credits, "Chorsu Bazaar in Tashkent.jpg")

    def test_crafts_lesson_shows_tiles_crafts_silk_and_a_match_game(self):
        # T234 (Michael, 2026-10-12): 'Silk Road crafts and blue tiles': Samarkand tiles, suzani, atlas silk, a match-the-craft game.
        item = self.course.items.get(activity__slug="uz-crafts-lesson")
        url = reverse("activity", args=[item.id])
        en = self.client.get(url + "?lang=en")
        self.assertContains(en, "Made by hand on the Silk Road")
        for img in ("uz-tiles", "uz-suzani", "uz-atlas", "uz-doppi", "uz-lagan", "uz-cocoons"):
            self.assertContains(en, f"img/photo/uzbekistan/{img}.jpg")
        for word in ("kok", "suzani", "atlas", "doppi", "lagan", "ipak"):
            self.assertContains(en, f"audio/uzbekistan/{word}.mp3")
        self.assertContains(en, "Ko&#x27;k")
        game = en.content.decode().rsplit("lpage-pick", 1)[1].split("data-game-msg", 1)[0]
        self.assertEqual(game.count('class="choice"'), 16)
        he = self.client.get(url + "?lang=he")
        self.assertContains(he, "עבודת יד על דרך המשי")
        self.assertContains(he, 'Ipak</span><span class="say-sub"><span class="he-say" lang="he">איפק</span>')
        credits = self.client.get(reverse("credits"))
        self.assertContains(credits, "Shahrisyabz suzani")

    def test_uzbek_screens_show_tuya_the_camel_and_japan_keeps_the_deer(self):
        # T234: Uzbekistan has its own guide, so its 'Great job!' page has a picture (it was an empty box).
        from django.template.loader import render_to_string
        self.assertIn('class="guide hero-guide"', render_to_string("includes/guides/uzbekistan.html", {"cls": "hero-guide"}))
        html = self.client.get(reverse("course")).content.decode()
        self.assertIn("var(--guide-camel)", html)
        self.assertNotIn("var(--guide-antler)", html)


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

    @staticmethod
    def spelling_clashes(docs):
        """T220: one word, one Hebrew spelling. Returns the readings with two spellings, and the cards whose label is
        the reading but whose label_he differs from reading_hebrew (the flip card then shows both)."""
        seen, clashes = {}, []

        def walk(node, name):
            if isinstance(node, dict):
                reading, he = node.get("reading"), node.get("reading_hebrew")
                if isinstance(reading, str) and isinstance(he, str):
                    key = reading.strip().lower()
                    first = seen.setdefault(key, (he, name))
                    if first[0] != he:
                        clashes.append(f"{key}: {first[0]} ({first[1]}) / {he} ({name})")
                    label = node.get("label")
                    if isinstance(label, str) and label.lower() == key and node.get("label_he") not in (None, he):
                        clashes.append(f"{key}: label_he {node['label_he']} / reading_hebrew {he} ({name})")
                for v in node.values():
                    walk(v, name)
            elif isinstance(node, list):
                for v in node:
                    walk(v, name)

        for name, doc in docs:
            walk(doc, name)
        return clashes

    def test_one_hebrew_spelling_per_word(self):
        root = Path(settings.BASE_DIR) / "content"
        docs = [(p.relative_to(root).as_posix(), yaml.safe_load(p.read_text())) for p in sorted(root.glob("**/*.yaml"))]
        self.assertEqual(self.spelling_clashes(docs), [])
        planted = [("a.yaml", {"reading": "gunkan", "reading_hebrew": "גונקאן"}),
                   ("b.yaml", [{"label": "Gunkan", "label_he": "גונקאן", "reading": "Gunkan", "reading_hebrew": "גונקן"}])]
        self.assertEqual(len(self.spelling_clashes(planted)), 2)

    def page(self, course, slug, lang):
        return self.client.get(reverse("activity", args=[course.items.get(activity__slug=slug).id]) + f"?lang={lang}").content.decode()

    def test_hebrew_word_line_and_no_hebrew_in_english(self):
        self.client.force_login(self.user)
        food = self.page(self.uz, "uz-food-lesson", "he")
        self.assertIn('Osh</span><span class="say-sub"><span class="he-say" lang="he">אוש</span>', food)
        words = self.page(self.uz, "uz-words-lesson", "he")
        self.assertIn('Rahmat</span><span class="say-sub"><span class="he-say" lang="he">רחמת</span>', words)
        for slug in ("uz-food-lesson", "uz-words-lesson", "uz-places-lesson", "uz-bazaar-lesson", "uz-crafts-lesson"):
            self.assertNotIn("he-say", self.page(self.uz, slug, "en"), slug)

    def test_hero_word_is_two_lines_kana_then_reading_and_speaker(self):
        # T224: line 1 holds the kana alone; line 2 holds the reading, the Hebrew spelling and the speaker.
        import re
        self.client.force_login(self.user)
        for slug in ("uz-food-lesson", "uz-words-lesson"):
            for lang in ("en", "he"):
                html = self.page(self.uz, slug, lang)
                heroes = re.findall(r'<p class="jp say-word hero-word".*?</p>', html)
                self.assertTrue(heroes, (slug, lang))
                for hero in heroes:
                    kana = re.search(r'<span class="say-kana">(.*?)</span>(<span class="say-sub">|</p>)', hero)
                    self.assertTrue(kana, hero)
                    self.assertNotIn("he-say", kana.group(1))
                    self.assertEqual(hero.count('class="say-mark"'), 1, hero)
                    if lang == "en":
                        self.assertNotIn("say-sub", hero)
                    else:
                        self.assertIn('<span class="say-sub"><span class="he-say"', hero)

    def test_japan_words_cards_show_the_hebrew_spelling(self):
        self.client.force_login(self.jp_user)
        item = self.jp.items.filter(activity__type="words").first()
        url = reverse("activity", args=[item.id])
        he = self.client.get(url + "?lang=he").content.decode()
        self.assertIn('konnichiwa</h3>\n    <p class="he-say reading-he" lang="he">קוניצ\'יווה</p>', he.replace("&#x27;", "'"))
        self.assertNotIn("he-say", self.client.get(url + "?lang=en").content.decode())
