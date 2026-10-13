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
from courses.models import Course
from trips.models import Traveller, Trip
from .testutil import item_for

CONTENT = Path(settings.BASE_DIR) / "content" / "uzbekistan"
# Every content file: each native word with a reading carries reading_hebrew (T200, T201).
ALL_CONTENT = Path(settings.BASE_DIR) / "content"


def _main_text(response):
    """The page body without the head (the site title) and without inline SVG drawings (path numbers)."""
    import re
    html = response.content.decode().split("<body", 1)[1]
    return re.sub(r"<svg.*?</svg>", "", html, flags=re.S)


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
        # T282 added 'Street View hunt' (streetview.yaml: a lesson and two hunts) and 'Staying safe' (safety.yaml).
        modules = Module.objects.filter(country="uzbekistan", ready=True)
        self.assertEqual(sorted(m.slug for m in modules), ["bazaar", "crafts", "food", "places", "safety", "streetview", "words"])
        for act in Activity.objects.filter(module__country="uzbekistan", type="lesson"):
            self.assertTrue(3 <= len(act.data["pages"]) <= 5, act.slug)
        hunts = Activity.objects.filter(module__country="uzbekistan").exclude(type="lesson")
        self.assertEqual(sorted(a.slug for a in hunts), ["uz-hunt-kalyan", "uz-hunt-registan"])
        self.assertEqual({a.type for a in hunts}, {"streetview"})
        self.assertEqual(self.course.items.count(), Activity.objects.filter(module__country="uzbekistan").count())

    def test_trip_form_offers_uzbekistan_and_keeps_other_places_coming_soon(self):
        page = self.client.get(reverse("trip_setup"))
        self.assertContains(page, 'name="destination" value="uzbekistan"')
        self.assertNotContains(page, 'name="destination" value="georgia"')
        self.assertContains(page, "Coming soon")
        other = get_user_model().objects.create_user("uz2@example.com", "uz2@example.com")
        self.client.force_login(other)
        # T264: the setup page holds both countries' module switches; the chosen country's modules build the course.
        setup = self.client.get(reverse("trip_setup")).content.decode()
        self.assertIn("Uzbek words", setup.split('data-modules-for="uzbekistan"')[1])
        self.assertNotIn("Japanese words", setup.split('data-modules-for="uzbekistan"')[1])
        r = self.client.post(reverse("trip_setup"), {"destination": "uzbekistan", "grownup": 2, "kid": 1})
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)
        trip = Trip.objects.get(user=other)
        self.assertEqual(trip.destination, "uzbekistan")
        self.assertTrue(Course.objects.get(trip=trip).module_ids)

    def test_every_word_has_sound_every_photo_has_credit_every_answer_is_a_choice(self):
        credits = load_photo_credits()
        for path in CONTENT.glob("*.yaml"):
            for act in yaml.safe_load(path.read_text())["activities"]:
                if act["type"] == "streetview":
                    continue  # a hunt has spots, not pictures; see test_street_view_hunts_*
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
        self.assertContains(page, "Our adventure in Uzbekistan")
        self.assertNotContains(page, "Our adventure in Japan")
        self.assertNotContains(page, "We are in Japan now")
        self.assertNotContains(page, ">In Japan<")
        he = self.client.get(reverse("course") + "?lang=he")
        self.assertContains(he, "ההרפתקה שלנו באוזבקיסטן")

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

    def test_street_view_hunts_open_registan_and_kalyan_with_five_spots_or_fewer(self):
        # T282 (Michael, 2026-10-13): a Street View hunt for Uzbekistan. The places were probed on 2026-10-13.
        for slug, place, lat in (("uz-hunt-registan", "Registan Square, Samarkand", "39.6548"),
                                 ("uz-hunt-kalyan", "Kalyan Mosque, Bukhara", "39.776")):
            item = self.course.items.get(activity__slug=slug)
            act = item.activity
            self.assertTrue(4 <= len(act.data["spots"]) <= 5, slug)
            for spot in act.data["spots"]:
                self.assertTrue(spot["name_he"] and spot["text_he"] and spot["about_he"], spot["name"])
            en = self.client.get(reverse("activity", args=[item.id]) + "?lang=en")
            self.assertContains(en, place)
            self.assertContains(en, lat)
            self.assertNotIn("Japan", _main_text(en))
            he = self.client.get(reverse("activity", args=[item.id]) + "?lang=he")
            self.assertContains(he, act.data["spots"][0]["name_he"])
        lesson = self.course.items.get(activity__slug="uz-street-lesson")
        page = self.client.get(reverse("activity", args=[lesson.id]) + "?lang=en")
        self.assertContains(page, "Towers, domes and tigers")
        self.assertContains(page, "img/photo/uzbekistan/uz-sherdor.jpg")
        self.assertContains(self.client.get(reverse("credits")), "Sher-Dor Madrasah Samarkand close-up.jpg")

    def test_safety_lesson_teaches_101_102_103_the_bazaar_water_and_the_name_card(self):
        # T282 (Michael, 2026-10-13): numbers checked on GOV.UK 2026-10-13: 101 fire, 102 police, 103 ambulance.
        item = self.course.items.get(activity__slug="uz-safety-lesson")
        url = reverse("activity", args=[item.id])
        en = self.client.get(url + "?lang=en")
        for text in ("Fire: 101", "Police: 102", "Ambulance: 103", "Stay together at the bazaar",
                     "Drink water from a bottle", "A name card in every pocket", "1173"):
            self.assertContains(en, text)
        self.assertNotIn("110", _main_text(en))  # the Japan numbers
        self.assertNotIn("119", _main_text(en))
        game = en.content.decode().rsplit("lpage-pick", 1)[1].split("data-game-msg", 1)[0]
        self.assertEqual(game.count('class="choice"'), 14)  # T294: the two number rounds offer 3 numbers only
        he = self.client.get(url + "?lang=he")
        self.assertContains(he, "בטוחים כמו ילדים באוזבקיסטן")
        self.assertContains(he, "שותים מים מבקבוק")

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

    def test_highlights_show_each_uzbek_word_once_with_a_meaning(self):
        """T221: 'Salom' over 'salom' was one word printed twice; Somsa had an empty meaning line."""
        from courses.highlights import met_words
        from practice.items import add_items
        for act in Activity.objects.filter(module__country="uzbekistan"):
            add_items(self.trip, act)
        words = [w["entry"] for w in met_words(self.trip)]
        self.assertGreaterEqual(len(words), 8)
        self.assertTrue(all(w["meaning"] for w in words), [(w["japanese"], w["meaning"]) for w in words])
        self.assertFalse(any(w["show_reading"] for w in words))
        en = self.client.get(reverse("highlights")).content.decode()
        self.assertNotIn('<h3 class="reading">salom', en)
        self.assertIn('lang="uz">Salom', en.replace("\n", ""))
        self.assertIn('<p class="meaning">Somsa, a meat pastry</p>', en)
        self.assertNotIn('<p class="meaning"></p>', en)
        self.assertNotIn('class="he-say', en)
        he = self.client.get(reverse("highlights") + "?lang=he").content.decode()
        self.assertIn('<p class="he-say reading-he" lang="he">סלום</p>', he)
        grid = he[he.find("word-grid"):]
        # Every card, also the text-page words Registon and Bozor, carries its Hebrew spelling.
        self.assertEqual(grid.count('class="card word'), grid.count('class="he-say reading-he"'))
        self.assertIn(">רגיסטון</p>", grid)
        self.assertIn('<p class="meaning">סומסה, מאפה בשר</p>', he)
        self.assertNotIn('<p class="meaning"></p>', he)
        self.assertNotIn('lang="ja"', he.split("Words we met")[-1] if "Words we met" in he else he[he.find("word-grid"):])

    def test_uzbek_screens_show_tuya_the_camel_and_japan_keeps_the_deer(self):
        # T234: Uzbekistan has its own guide, so its 'Great job!' page has a picture (it was an empty box).
        from django.template.loader import render_to_string
        self.assertIn('class="guide hero-guide"', render_to_string("includes/guides/uzbekistan.html", {"cls": "hero-guide"}))
        html = self.client.get(reverse("course")).content.decode()
        self.assertIn("var(--guide-camel)", html)
        self.assertNotIn("var(--guide-antler)", html)


    def test_uzbekistan_is_marked_work_in_progress(self):
        # Feedback T261 (Michael 2026-10-13): a clear 'work in progress' badge on its card and its course pages, en + he.
        item = self.course.items.get(activity__slug="uz-words-lesson")
        words = (("en", "Work in progress"), ("he", "עדיין בבנייה"))
        for lang, word in words:
            self.assertContains(self.client.get(reverse("course") + f"?lang={lang}"), word)
            self.assertContains(self.client.get(reverse("activity", args=[item.id]) + f"?lang={lang}"), word)
            # The trip form: only the Uzbekistan card has it.
            self.assertContains(self.client.get(reverse("trip_setup") + f"?lang={lang}"), word, count=1)
        self.client.logout()
        for lang, word in words:
            self.assertContains(self.client.get(reverse("home") + f"?lang={lang}"), word, count=1)

    def test_japan_pages_have_no_work_in_progress_badge(self):
        jp_user = get_user_model().objects.create_user("jp@example.com", "jp@example.com")
        jp_trip = Trip.objects.create(user=jp_user, destination="japan")
        Traveller.objects.create(trip=jp_trip, age=38)
        jp_course = build_course(jp_trip, list(Module.objects.filter(country="japan", ready=True).values_list("id", flat=True)))
        self.client.force_login(jp_user)
        self.assertNotContains(self.client.get(reverse("course") + "?lang=en"), "Work in progress")
        jp_item = jp_course.next_item()
        self.assertNotContains(self.client.get(reverse("activity", args=[jp_item.id]) + "?lang=en"), "Work in progress")

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

    def test_every_native_word_has_a_hebrew_spelling(self):
        def dicts(node):
            if isinstance(node, dict):
                yield node
                for v in node.values():
                    yield from dicts(v)
            elif isinstance(node, list):
                for v in node:
                    yield from dicts(v)

        def has_hebrew(d):
            # A game item with no reading line says the word through say_he or label_he instead.
            if d.get("reading"):
                return bool(d.get("reading_hebrew"))
            return bool(d.get("reading_hebrew") or d.get("say_he") or d.get("label_he"))

        missing = [f"{path.relative_to(ALL_CONTENT)}: {d['japanese']}" for path in sorted(ALL_CONTENT.glob("**/*.yaml"))
                   for d in dicts(yaml.safe_load(path.read_text())) if d.get("japanese") and not has_hebrew(d)]
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
        item = item_for(self.jp, "words-intro")
        url = reverse("activity", args=[item.id])
        he = self.client.get(url + "?lang=he").content.decode()
        self.assertIn('konnichiwa</h3>\n    <p class="he-say reading-he" lang="he">קוניצ\'יווה</p>', he.replace("&#x27;", "'"))
        self.assertNotIn("he-say", self.client.get(url + "?lang=en").content.decode())


class NoGuideFallbackTests(TestCase):
    """T206: a country with no guide shows the app mark on hero spots, so 'Great job!' keeps its top picture."""

    def test_hero_spot_falls_back_to_the_mark_and_title_stays_empty(self):
        from django.template.loader import render_to_string
        hero = render_to_string("includes/guide.html", {"country_guide": "", "cls": "hero-guide cheer"})
        self.assertIn('class="guide mark hero-guide cheer"', hero)
        self.assertEqual(render_to_string("includes/guide.html", {"country_guide": "", "cls": "title-guide"}).strip(), "")

    def test_japan_keeps_the_deer_and_uzbekistan_the_camel(self):
        from django.template.loader import render_to_string
        from tripapp.guides import GUIDES
        jp = render_to_string("includes/guide.html", {"country_guide": GUIDES["japan"], "cls": "hero-guide"})
        self.assertIn("var(--guide-antler)", jp)
        self.assertNotIn("guide mark", jp)
        uz = render_to_string("includes/guide.html", {"country_guide": GUIDES["uzbekistan"], "cls": "hero-guide"})
        self.assertIn("var(--guide-camel)", uz)
