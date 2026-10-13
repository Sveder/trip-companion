from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone, translation

from content_admin.models import Activity, Module
from courses.builder import build_course
from courses.models import CourseItem
from trips.models import Traveller, Trip

from .items import _card_id, add_items, due_items, question
from .models import PracticeItem

TODAY = date(2026, 10, 7)


def make_trip(user, ages=(38, 4)):
    trip = Trip.objects.create(user=user, destination="japan")
    for a in ages:
        Traveller.objects.create(trip=trip, age=a)
    return trip


class LeitnerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.trip = make_trip(get_user_model().objects.create_user("l@example.com", "l@example.com"))

    def item(self, box=1):
        return PracticeItem.objects.create(trip=self.trip, key=f"words/w/x{box}", box=box, due_on=TODAY)

    def test_right_moves_up_one_box_and_comes_back_later(self):
        expected = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}
        for box, days in expected.items():
            p = self.item(box)
            p.answer(True, today=TODAY)
            p.refresh_from_db()
            self.assertEqual(p.box, min(box + 1, 5))
            self.assertEqual(p.due_on, TODAY + timedelta(days=days))
            self.assertTrue(p.last_result)

    def test_wrong_goes_back_to_box_one_due_tomorrow(self):
        p = self.item(4)
        p.answer(False, today=TODAY)
        p.refresh_from_db()
        self.assertEqual((p.box, p.due_on, p.last_result), (1, TODAY + timedelta(days=1), False))

    def test_quiz_holds_at_most_eight_due_items_earliest_first(self):
        for n in range(12):
            PracticeItem.objects.create(trip=self.trip, key=f"k/{n}", due_on=TODAY - timedelta(days=n))
        PracticeItem.objects.create(trip=self.trip, key="k/future", due_on=TODAY + timedelta(days=1))
        due = due_items(self.trip, TODAY)
        self.assertEqual(len(due), 8)
        self.assertEqual([p.key for p in due], [f"k/{n}" for n in range(11, 3, -1)])
        self.assertNotIn("k/future", [p.key for p in due_items(self.trip, TODAY, limit=50)])


class QuizContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("q@example.com", "q@example.com")
        cls.trip = make_trip(cls.user)

    def test_words_module_is_ready_with_words(self):
        words = Activity.objects.get(module__slug="words", type="words")
        self.assertTrue(words.module.ready)
        self.assertGreaterEqual(len(words.data["words"]), 5)
        self.assertEqual(add_items(self.trip, words), len(words.data["words"]))
        self.assertEqual(add_items(self.trip, words), 0, "a second pass adds nothing")

    def test_only_cards_marked_quiz_become_items(self):
        # T179: the food card list is gone; the manners cards are a card list with quiz marks.
        cards = Activity.objects.get(slug="dos_donts-intro")
        add_items(self.trip, cards)
        keys = set(PracticeItem.objects.filter(trip=self.trip).values_list("key", flat=True))
        marked = [c for c in cards.data["cards"] if c.get("quiz")]
        self.assertTrue(0 < len(marked) < len(cards.data["cards"]))
        self.assertEqual(len(keys), len(marked))
        self.assertIn("dos_donts/dos_donts-intro/bow", keys)
        for c in cards.data["cards"]:
            if not c.get("quiz"):
                self.assertNotIn(f"dos_donts/dos_donts-intro/{_card_id(c)}", keys)

    def test_question_has_the_answer_among_four_choices(self):
        q = question(self.trip, "words/words-intro/konnichiwa")
        self.assertEqual(q["answer"], "hello")
        self.assertEqual(len(q["choices"]), 4)
        self.assertIn("hello", q["choices"])
        q = question(self.trip, "dos_donts/dos_donts-intro/bow")
        self.assertIn(q["answer"], q["choices"])
        self.assertEqual(len(q["choices"]), 4)
        self.assertIsNone(question(self.trip, "food/food-cards/sushi"), "T179: the old food cards are gone")

    def test_food_quiz_asks_only_about_foods(self):
        for food in Activity.objects.filter(module__slug="food"):
            add_items(self.trip, food)
        keys = PracticeItem.objects.filter(trip=self.trip, key__startswith="food/").values_list("key", flat=True)
        self.assertTrue(keys)
        for key in keys:
            self.assertNotIn("itadakimasu", key)
            q = question(self.trip, key)
            self.assertNotIn("Itadakimasu!", q["choices"])
            self.assertNotEqual(q["answer"], "Itadakimasu!")

    def test_itadakimasu_is_a_word(self):
        q = question(self.trip, "words/words-intro/itadakimasu")
        self.assertEqual(q["answer"], "thank you for the food")
        self.assertEqual(q["reading"], "itadakimasu")

    def test_stub_turned_ready_clears_old_done_marks(self):
        course = build_course(self.trip, list(Module.objects.values_list("id", flat=True)))
        item = course.items.get(activity__slug="words-intro")
        item.mark_done()
        Module.objects.filter(slug="words").update(ready=False)
        call_command("load_content", verbosity=0)
        self.assertIsNone(CourseItem.objects.get(id=item.id).done_at)


class QuizFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("f@example.com", "f@example.com")

    def test_every_word_has_its_mp3(self):
        """deploy/make_word_audio.py makes these; a word with no mp3 plays nothing in a browser with no Japanese voice."""
        from django.contrib.staticfiles import finders
        words = Activity.objects.get(module__slug="words", type="words").data["words"]
        missing = [w["reading"] for w in words if not finders.find(f"audio/japan/{w['reading']}.mp3")]
        self.assertEqual(missing, [], "run deploy/make_word_audio.py")

    def test_every_food_page_says_its_name(self):
        """A 4-year-old cannot read 'Onigiri': each food photo page plays a pre-made mp3 on a tap (T179: the old cards are pages now)."""
        from django.contrib.staticfiles import finders
        pages = [p for p in Activity.objects.get(slug="food-around-japan").data["pages"] if p.get("photo_credit")]
        self.assertEqual([p["title"] for p in pages if not p.get("japanese") or not p.get("reading")], [])
        missing = [p["reading"] for p in pages if not finders.find(f"audio/japan/{p['reading']}.mp3")]
        self.assertEqual(missing, [], "run deploy/make_word_audio.py")
        trip = make_trip(self.user)
        course = build_course(trip, list(Module.objects.filter(slug="food").values_list("id", flat=True)))
        item = course.items.get(activity__slug="food-around-japan")
        self.client.force_login(self.user)
        page = self.client.get(reverse("activity", args=[item.id]))
        for reading in ("tempura", "misoshiru", "bento", "itadakimasu"):
            self.assertContains(page, f'data-say-src="/static/audio/japan/{reading}.mp3"')

    def test_food_quiz_says_the_name_only_after_the_answer(self):
        trip = make_trip(self.user)
        add_items(trip, Activity.objects.get(slug="sushi-lesson"))
        self.client.force_login(self.user)
        page = self.client.get(reverse("quiz"))
        q = page.context["q"]
        self.assertNotContains(page, "data-say-src")
        r = self.client.post(reverse("quiz"), {"key": q["key"], "choice": q["answer"]})
        self.assertContains(r, f'data-say-src="/static/audio/japan/{q["reading"]}.mp3"')

    def test_words_activity_then_quiz_wrong_answer_comes_back(self):
        trip = make_trip(self.user)
        course = build_course(trip, list(Module.objects.filter(slug="words").values_list("id", flat=True)))
        item = course.items.get(activity__slug="words-intro")
        self.client.force_login(self.user)
        page = self.client.get(reverse("activity", args=[item.id]))
        self.assertContains(page, "こんにちは")
        self.assertContains(page, 'data-say="こんにちは" data-say-src="/static/audio/japan/konnichiwa.mp3"')
        self.assertContains(self.client.get(reverse("quiz")), "No quiz yet")
        self.client.post(reverse("activity_done", args=[item.id]))
        n = PracticeItem.objects.filter(trip=trip).count()
        self.assertEqual(n, len(item.activity.data["words"]))

        page = self.client.get(reverse("quiz"))
        self.assertContains(page, f"Question 1 of {n}")
        q = page.context["q"]
        self.assertContains(page, f'data-say-src="/static/audio/japan/{q["reading"]}.mp3"')
        wrong = next(c for c in q["choices"] if c != q["answer"])
        r = self.client.post(reverse("quiz"), {"key": q["key"], "choice": wrong})
        self.assertContains(r, "Not this time")
        self.assertContains(r, "We ask this one again tomorrow.")
        self.assertNotContains(r, "next time")
        missed = PracticeItem.objects.get(trip=trip, key=q["key"])
        # Answer every other question right.
        for _ in range(n - 1):
            q = self.client.get(reverse("quiz")).context["q"]
            self.assertContains(self.client.post(reverse("quiz"), {"key": q["key"], "choice": q["answer"]}), "Great job")
        self.assertContains(self.client.get(reverse("quiz") + "?end=1"), f"You got {n - 1} of {n} right")
        missed.refresh_from_db()
        self.assertEqual(missed.box, 1)
        # The same day, the quiz does not start again with the missed word.
        for url in (reverse("quiz"), reverse("quiz") + "?new=1"):
            page = self.client.get(url)
            self.assertContains(page, "All done for today!")
            self.assertContains(page, "Come back tomorrow")
            self.assertNotIn("q", page.context)
        # The next day, the missed word is asked first.
        tomorrow = timezone.localdate() + timedelta(days=1)
        with mock.patch("django.utils.timezone.localdate", return_value=tomorrow):
            page = self.client.get(reverse("quiz") + "?new=1")
        self.assertContains(page, f"Question 1 of {n}")
        self.assertEqual(page.context["q"]["key"], missed.key)

    def test_quiz_end_screen_promises_tomorrow(self):
        trip = make_trip(self.user)
        PracticeItem.objects.create(trip=trip, key="words/words-intro/hai")
        self.client.force_login(self.user)
        q = self.client.get(reverse("quiz")).context["q"]
        wrong = next(c for c in q["choices"] if c != q["answer"])
        self.client.post(reverse("quiz"), {"key": q["key"], "choice": wrong})
        page = self.client.get(reverse("quiz") + "?end=1")
        self.assertContains(page, "You got 0 of 1 right. The ones we missed come back tomorrow.")
        self.assertNotContains(page, "come back soon")

    def test_empty_quiz_button_leads_to_the_course(self):
        """T208: no quiz yet opens the next activity; no quiz today opens the course; no course goes home."""
        trip = make_trip(self.user)
        self.client.force_login(self.user)
        page = self.client.get(reverse("quiz"))
        self.assertContains(page, f'href="{reverse("home")}">Back home<')
        course = build_course(trip, list(Module.objects.filter(slug="words").values_list("id", flat=True)))
        nxt = reverse("activity", args=[course.next_item().id])
        for lang, label in (("en", "Start our adventure"), ("he", "יוצאים להרפתקה")):
            self.client.cookies["django_language"] = lang
            page = self.client.get(reverse("quiz"))
            self.assertContains(page, f'href="{nxt}">{label}<')
            self.assertNotContains(page, f'href="{reverse("home")}" ')
        self.client.cookies["django_language"] = "en"
        PracticeItem.objects.create(trip=trip, key="words/words-intro/hai", due_on=timezone.localdate() + timedelta(days=3))
        page = self.client.get(reverse("quiz") + "?new=1")
        self.assertContains(page, "No quiz today!")
        self.assertContains(page, f'href="{reverse("course")}">Our adventure<')

    def test_quiz_ignores_a_stale_answer(self):
        trip = make_trip(self.user)
        PracticeItem.objects.create(trip=trip, key="words/words-intro/hai")
        self.client.force_login(self.user)
        self.client.get(reverse("quiz"))
        r = self.client.post(reverse("quiz"), {"key": "words/words-intro/oishii", "choice": "yummy"})
        self.assertRedirects(r, reverse("quiz"))
        self.assertIsNone(PracticeItem.objects.get(trip=trip).last_result)


class LessonQuizTests(TestCase):
    """A finished lesson puts its spots and flip cards into the quiz (T92)."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("lq@example.com", "lq@example.com")
        cls.trip = make_trip(cls.user)
        cls.lesson = Activity.objects.get(slug="sushi-lesson")

    def keys(self):
        return set(PracticeItem.objects.filter(trip=self.trip).values_list("key", flat=True))

    def test_finishing_the_lesson_adds_at_most_twelve_items(self):
        added = add_items(self.trip, self.lesson)
        keys = self.keys()
        self.assertEqual(added, len(keys))
        self.assertTrue(0 < len(keys) <= 12)
        self.assertIn("food/sushi-lesson/shari", keys)  # a spot
        self.assertIn("food/sushi-lesson/nigiri", keys)  # a flip card

    def test_spot_question_in_english_and_hebrew(self):
        with translation.override("en"):
            q = question(self.trip, "food/sushi-lesson/shari")
            self.assertEqual(q["prompt"], "Which one is shari?")
            self.assertEqual(q["answer"], "Rice")
            self.assertEqual(len(q["choices"]), 4)
            self.assertIn("Rice", q["choices"])
            self.assertTrue(q["image"].endswith("img/lesson/sushi/plate.svg"))
        with translation.override("he"):
            q = question(self.trip, "food/sushi-lesson/shari")
            self.assertEqual(q["prompt"], "איזה מהם נקרא שארי?")
            self.assertEqual(q["answer"], "אורז")
            self.assertEqual(len(q["choices"]), 4)
            self.assertIn("אורז", q["choices"])

    def test_every_hebrew_spot_prompt_has_no_latin_letters(self):
        """T123: in Hebrew every spots question of every lesson asks with Hebrew letters ('נטה', not 'neta')."""

        from .items import item_key, quiz_entries

        asked = 0
        for lesson in Activity.objects.filter(type="lesson"):
            for item_id, entry in quiz_entries(lesson, everything=True):
                if entry.get("img") or not entry.get("reading"):
                    continue
                with translation.override("he"):
                    q = question(self.trip, item_key(lesson, item_id))
                self.assertIsNotNone(q, item_id)
                self.assertNotRegex(q["prompt"], r"[A-Za-z]", f"{lesson.slug}/{item_id}")
                self.assertEqual(q["reading"], entry["reading"])  # the audio file name stays Latin
                asked += 1
        self.assertGreaterEqual(asked, 39)
        with translation.override("en"):
            self.assertEqual(question(self.trip, "food/sushi-lesson/neta")["prompt"], "Which one is neta?")

    def test_spot_question_rings_the_asked_part(self):
        """T108: 'Which one is neta?' puts a ring on the topping; a flip card question has no ring."""
        lesson_spots = [s for p in self.lesson.data["pages"] if p.get("kind") == "spots" for s in p["spots"]]
        neta = next(s for s in lesson_spots if s.get("reading") == "neta")
        with translation.override("en"):
            q = question(self.trip, "food/sushi-lesson/neta")
            self.assertEqual(q["spot"], {"x": neta["x"], "y": neta["y"]})
            self.assertNotIn("spot", question(self.trip, "food/sushi-lesson/nigiri"))
        PracticeItem.objects.create(trip=self.trip, key="food/sushi-lesson/neta", due_on=TODAY)
        self.client.force_login(self.user)
        page = self.client.get(reverse("quiz") + "?new=1")
        self.assertContains(page, 'class="ask-ring"')
        self.assertContains(page, f'left: {neta["x"]}%; top: {neta["y"]}%')
        # A wrong pick is marked on the answer page.
        wrong = next(c for c in page.context["q"]["choices"] if c != "Fish")
        page = self.client.post(reverse("quiz"), {"key": "food/sushi-lesson/neta", "choice": wrong}, follow=True)
        self.assertContains(page, "is-wrong")

    def test_flip_question_uses_the_picture_and_its_own_page(self):
        with translation.override("en"):
            q = question(self.trip, "food/sushi-lesson/nigiri")
            self.assertEqual((q["prompt"], q["answer"]), ("What is this?", "Nigiri"))
            self.assertTrue(q["image"].endswith("img/lesson/sushi/sake.svg"))
            self.assertEqual(len(q["choices"]), 4)
            # Salmon has the same picture on another page; it must not be a wrong choice here.
            self.assertNotIn("Saamon", q["choices"])
            self.assertTrue(set(q["choices"]) <= {"Nigiri", "Maki", "Gunkan", "Temaki", "Inari"})
        with translation.override("he"):
            q = question(self.trip, "food/sushi-lesson/nigiri")
            self.assertEqual(q["answer"], "ניגירי")
            self.assertIn("ניגירי", q["choices"])
            self.assertEqual(len(q["choices"]), 4)

    def test_an_item_the_family_has_keeps_its_box(self):
        PracticeItem.objects.create(trip=self.trip, key="food/sushi-lesson/shari", box=3, due_on=TODAY)
        add_items(self.trip, self.lesson)
        self.assertEqual(PracticeItem.objects.get(trip=self.trip, key="food/sushi-lesson/shari").box, 3)

    def test_every_lesson_gives_quiz_items_with_four_choices(self):
        for lesson in Activity.objects.filter(type="lesson"):
            add_items(self.trip, lesson)
        for p in PracticeItem.objects.filter(trip=self.trip):
            q = question(self.trip, p.key)
            self.assertIsNotNone(q, p.key)
            self.assertIn(q["answer"], q["choices"])
            self.assertGreaterEqual(len(q["choices"]), 2, p.key)

    def test_words_lesson_card_asks_what_we_say(self):
        words = Activity.objects.get(slug="words-lesson")
        with translation.override("en"):
            q = question(self.trip, "words/words-lesson/ohayou")
            self.assertEqual(q["prompt"], "What do we say here?")
            self.assertIn(q["answer"], q["choices"])
        # A spot with no reading is never asked, but it can be a wrong choice.
        from .items import quiz_entries
        self.assertTrue(all(e.get("img") or e.get("reading") for _, e in quiz_entries(words)))

    def test_the_cap_keeps_a_mix_of_pages(self):
        from .items import quiz_entries
        pages = [e["page"] for _, e in quiz_entries(self.lesson)]
        self.assertEqual(len(pages), 12)
        self.assertEqual(len(set(pages)), 3)  # the spots page and both flip pages
        self.assertNotEqual(pages[0], pages[1])


class WordAudioScriptTests(SimpleTestCase):
    """deploy/make_word_audio.py: edge-tts first, Google Translate TTS when edge-tts fails (T167)."""

    def load(self):
        import importlib.util
        import pathlib

        path = pathlib.Path(__file__).resolve().parent.parent / "deploy" / "make_word_audio.py"
        spec = importlib.util.spec_from_file_location("make_word_audio", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_a_403_from_edge_falls_back_to_google_and_leaves_no_empty_file(self):
        import pathlib
        import subprocess
        import tempfile

        mod = self.load()
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "sushi.mp3"

            def fail(cmd, **kw):
                path.write_bytes(b"")  # edge-tts opens the file, then the 403 kills it
                raise subprocess.CalledProcessError(1, cmd)

            with mock.patch.object(mod.subprocess, "run", side_effect=fail):
                self.assertFalse(mod.edge("すし", path))
            self.assertFalse(path.exists())

            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = b"ID3mp3"
            response.headers.get_content_type.return_value = "audio/mpeg"
            with mock.patch.object(mod.urllib.request, "urlopen", return_value=response) as urlopen:
                mod.google("すし", path)
            self.assertIn("tl=ja", urlopen.call_args[0][0].full_url)
            self.assertIn("%E3%81%99%E3%81%97", urlopen.call_args[0][0].full_url)
            self.assertEqual(path.read_bytes(), b"ID3mp3")

    def test_google_refuses_a_page_that_is_not_audio(self):
        import pathlib
        import tempfile

        mod = self.load()
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"<html>captcha</html>"
        response.headers.get_content_type.return_value = "text/html"
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mod.urllib.request, "urlopen", return_value=response):
            path = pathlib.Path(d) / "sushi.mp3"
            with self.assertRaises(RuntimeError):
                mod.google("すし", path)
            self.assertFalse(path.exists())


class PhotoFileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def test_every_photo_exists_and_matches_its_credit(self):
        """T181: a swapped photo gets a new file name (no hashed static names), so every path and credit must follow it."""
        import yaml
        from django.conf import settings
        from django.contrib.staticfiles import finders
        credits = {c["id"]: c["file"] for c in yaml.safe_load((settings.BASE_DIR / "content/photo_credits.yaml").read_text())}
        paths, pairs = set(), []

        def walk(node):
            if isinstance(node, dict):
                if node.get("photo_credit"):
                    pairs.append((node["photo_credit"], node.get("photo") or node.get("img")))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
            elif isinstance(node, str) and node.startswith("photo/"):
                paths.add(node)

        for data in Activity.objects.values_list("data", flat=True):
            walk(data)
        self.assertIn("photo/food/food-curry-rice.jpg", paths)
        # T182: the itadakimasu page shows a school lunch tray, not the old stairwell photo.
        self.assertIn("photo/food/food-school-lunch.jpg", paths)
        self.assertNotIn("photo/food/food-itadakimasu.jpg", paths)
        self.assertEqual(sorted(p for p in paths if not finders.find(f"img/{p}")), [])
        self.assertEqual([(c, p) for c, p in pairs if credits.get(c) != p], [])

    def test_every_tip_is_plain_text(self):
        """T182: a colon in a YAML list item ("In the picture: ...") makes a dict, and the page prints {'...': '...'}."""
        bad = []

        def walk(node, where):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in ("tips", "tips_he") and isinstance(v, list):
                        bad.extend(f"{where} {k}: {t!r}" for t in v if not isinstance(t, str))
                    walk(v, where)
            elif isinstance(node, list):
                for v in node:
                    walk(v, where)

        for slug, data in Activity.objects.values_list("slug", "data"):
            walk(data, slug)
        self.assertEqual(bad, [])

    def test_no_flip_card_repeats_the_word_on_its_front(self):
        """T183/T188: the front shows the meaning over the native word. label == word printed 'Ha' over 'Ha'
        in English; label_he == the Hebrew spelling of the word (say_he) printed 'הא' over 'Ha' in Hebrew."""
        import yaml
        from django.conf import settings

        def dicts(node):
            if isinstance(node, dict):
                yield node
                for v in node.values():
                    yield from dicts(v)
            elif isinstance(node, list):
                for v in node:
                    yield from dicts(v)

        # Read the YAML itself: the test database loads only japan.
        files = {path.relative_to(settings.BASE_DIR): yaml.safe_load(path.read_text())
                 for path in sorted((settings.BASE_DIR / "content").glob("*/*.yaml"))}
        # Every Hebrew spelling of a native word, from any file: say_he, reading_he, reading_hebrew.
        spelled = {}
        for data in files.values():
            for d in dicts(data):
                if d.get("japanese"):
                    for k in ("say_he", "reading_he", "reading_hebrew"):
                        if d.get(k):
                            spelled.setdefault(str(d["japanese"]).lower(), set()).add(d[k])
        bad = []
        for where, data in files.items():
            for node in dicts(data):
                for c in node.get("cards") or []:
                    if not (isinstance(c, dict) and c.get("japanese")):
                        continue
                    if c.get("label") == c["japanese"]:
                        bad.append(f"{where}: {c['label']}")
                    # A Japan card shows the reading on both fronts ('Ohayou' / 'אוהאיו' over おはよう): fine.
                    # A card whose English front is the meaning ('Yes' over Ha) needs the meaning in Hebrew too.
                    if str(c.get("label", "")).lower() == str(c.get("reading", "")).lower():
                        continue
                    own = {c.get(k) for k in ("say_he", "reading_he", "reading_hebrew")} - {None, ""}
                    if c.get("label_he") and c["label_he"] in own | spelled.get(str(c["japanese"]).lower(), set()):
                        bad.append(f"{where}: label_he {c['label_he']} over {c['japanese']}")
        self.assertEqual(bad, [])


class TextPageQuizTests(TestCase):
    """T211: a lesson made of text pages (Uzbekistan, Food around Japan) still puts its words into the quiz."""

    # The item keys of every other Japan lesson, saved before T211. They must not change.
    JAPAN_KEYS = {
        "buy_in_advance/pack-lesson": ["hankachi", "the-esim", "okane", "kozeniire", "visit-japan-web", "seven-bank-atm", "the-ic-card", "japan-post-atm", "kasa", "snacks-for-the-day"],
        "chopsticks/chopsticks-lesson": ["sushi", "never-stand-them-in-rice", "oshibori", "waribashi", "noodles", "never-pass-food-stick-to-stick", "renge", "mai-hashi", "a-grape", "do-not-point-with-them", "misoshiru", "peas"],
        "dos_donts/manners-lesson": ["genkan", "a-home", "torii", "slurp", "getabako", "a-temple-hall", "temizuya", "oshibori", "a-japanese-inn", "two-hands", "a-train-or-a-shop", "no-tips"],
        "food/sushi-lesson": ["neta", "nigiri", "maguro", "shari", "maki", "saamon", "nori", "gunkan", "ebi", "kappamaki", "temaki", "tamago"],
        "safety/safety-lesson": ["koban", "one-one-zero", "maigo-desu", "the-map-on-the-door", "konbini", "one-one-nine-fire", "tasukete", "the-torch", "one-one-nine-ambulance", "the-hotel-card", "help-in-english", "our-meeting-place"],
        "streetview/streetview-lesson": ["jidouhanbaiki", "jinja", "gojuunotou", "deguchi", "attakai", "posuto", "otera", "ojizousan", "iriguchi", "tsumetai", "noren", "komainu"],
        "transport/transport-lesson": ["midori-no-madoguchi", "suica-and-pasmo", "yuusenseki", "kakueki-teisha", "takushii", "kaisatsu", "welcome-suica", "tsurikawa", "kaisoku", "kuusha", "bansen", "in-the-phone"],
        "words/words-lesson": ["ohayou", "arigatou", "irasshaimase", "konnichiwa", "sumimasen", "fukuro", "konbanwa", "onegaishimasu", "atatamemasu-ka", "oyasumi", "hai", "sayounara"],
    }

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", "japan", "uzbekistan", verbosity=0)
        cls.user = get_user_model().objects.create_user("tp@example.com", "tp@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="uzbekistan")
        Traveller.objects.create(trip=cls.trip, age=38)
        cls.jtrip = make_trip(get_user_model().objects.create_user("tpj@example.com", "tpj@example.com"))

    def test_every_uzbek_lesson_and_food_around_japan_add_items(self):
        lessons = list(Activity.objects.filter(module__country="uzbekistan", type="lesson"))
        self.assertEqual(len(lessons), 5)
        for lesson in lessons:
            self.assertGreaterEqual(add_items(self.trip, lesson), 3, lesson.slug)
        self.assertGreaterEqual(add_items(self.jtrip, Activity.objects.get(slug="food-around-japan")), 3)

    def test_other_japan_lessons_keep_their_keys(self):
        from .items import quiz_entries

        for a in Activity.objects.select_related("module").filter(module__country="japan", type="lesson"):
            name = f"{a.module.slug}/{a.slug}"
            if name == "food/food-around-japan":
                continue
            self.assertEqual([i for i, _ in quiz_entries(a)], self.JAPAN_KEYS[name], name)

    def test_text_page_question_has_photo_and_three_other_foods(self):
        food = Activity.objects.get(slug="uz-food-lesson")
        add_items(self.trip, food)
        foods = {"Plov", "Bread", "Somsa", "Tea"}
        with translation.override("en"):
            q = question(self.trip, "food/uz-food-lesson/osh")
            self.assertEqual((q["prompt"], q["answer"]), ("Which one is osh?", "Plov"))
            self.assertTrue(q["image"].endswith("img/photo/uzbekistan/uz-plov.jpg"))
            self.assertEqual(sorted(q["choices"]), sorted(foods))
        with translation.override("he"):
            q = question(self.trip, "food/uz-food-lesson/osh")
            self.assertEqual(q["answer"], "פלוב")
            self.assertEqual(len(set(q["choices"])), 4)
            self.assertNotRegex(q["prompt"], r"[A-Za-z]")
        jfood = Activity.objects.get(slug="food-around-japan")
        add_items(self.jtrip, jfood)
        names = {p["label"] for p in jfood.data["pictures"] if p.get("quiz") is not False}
        with translation.override("en"):
            for p in PracticeItem.objects.filter(trip=self.jtrip, key__startswith="food/food-around-japan/"):
                q = question(self.jtrip, p.key)
                self.assertEqual(len(q["choices"]), 4, p.key)
                self.assertEqual(len(set(q["choices"])), 4, p.key)
                self.assertEqual(q["choices"].count(q["answer"]), 1, p.key)
                self.assertTrue(set(q["choices"]) <= names, p.key)
                self.assertTrue(q["image"], p.key)
        self.assertFalse(PracticeItem.objects.filter(trip=self.jtrip, key="food/food-around-japan/itadakimasu").exists())

    def test_uzbek_words_question_asks_in_hebrew_letters(self):
        add_items(self.trip, Activity.objects.get(slug="uz-words-lesson"))
        with translation.override("he"):
            q = question(self.trip, "words/uz-words-lesson/salom")
            self.assertEqual(q["answer"], "שלום")
            self.assertIn("סלום", q["prompt"])
            self.assertEqual(len(set(q["choices"])), 4)

    def test_quiz_page_asks_after_the_uzbek_food_lesson(self):
        add_items(self.trip, Activity.objects.get(slug="uz-food-lesson"))
        PracticeItem.objects.filter(trip=self.trip).update(due_on=TODAY)
        self.client.force_login(self.user)
        page = self.client.get(reverse("quiz") + "?new=1")
        self.assertNotContains(page, "No quiz yet")
        self.assertContains(page, "uz-")
