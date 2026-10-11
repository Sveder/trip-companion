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

    def test_michael_feedback_t103(self):
        """Numbers sit beside the picture, cards keep one size, maki is drawn at an angle, the train speeds up 7% a round."""
        html = self.page()
        # (1) Each spot has a ring on the thing and a number button that JavaScript moves to the side.
        self.assertEqual(html.count('class="lspot-dot"'), html.count('class="lspot"'))
        self.assertIn('data-x="28" data-y="33"', html)
        self.assertIn('class="spot-infos"', html)
        root = Path(settings.BASE_DIR) / "static"
        js = (root / "js" / "lesson.js").read_text()
        self.assertIn("function placeSpots", js)
        self.assertIn("lpage-show", js)
        # (2) Both faces of a flip card share one grid cell, so a turn does not change the card height.
        css = (root / "css" / "app.css").read_text()
        self.assertIn(".flip-front, .flip-back { grid-area: 1 / 1;", css)
        self.assertNotIn(".flip-back { display: none", css)
        self.assertIn(".spot-info { grid-area: 1 / 1;", css)
        # (3) Maki: a cylinder (side path and a top ellipse), not two flat circles.
        maki = (root / "img" / "lesson" / "sushi" / "maki.svg").read_text()
        self.assertIn("<ellipse", maki)
        self.assertNotIn('<circle r="24"', maki)
        # (4) The belt: x1.07 per finished round, through playbackRate so the plates do not jump.
        self.assertIn("rate = Math.min(rate * 1.07, 2.5)", js)
        self.assertIn("playbackRate = rate", js)

    def test_michael_feedback_t157(self):
        """The belt is 30 percent faster (21 s), and 'Keep going!' starts endless rounds with a kept best score."""
        root = Path(settings.BASE_DIR) / "static"
        css = (root / "css" / "app.css").read_text()
        self.assertIn("animation: belt 21s linear infinite;", css)
        js = (root / "js" / "lesson.js").read_text()
        self.assertIn("localStorage.setItem(key", js)
        for lang, words in (("en", ["Keep going!", "Again", "Catch the {name}!", "You caught {n}! Best: {best}"]),
                            ("he", ["ממשיכים!", "עוד פעם", "תפסו: {name}!", "תפסתם {n}! השיא: {best}"])):
            html = self.page(lang)
            self.assertIn("data-keep-going", html)
            self.assertIn("data-endless", html)
            self.assertRegex(html, r'data-best-key="tc_best_\d+_\d+"')
            for w in words:
                self.assertIn(w, html, (lang, w))

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
        self.assertEqual(video["title"], "Watch sushi being made")
        self.assertIn("Watch the video", video["text"])

    def test_unapproved_video_uses_the_fallback_title_and_text(self):
        """T107: a page with no approved video does not promise one."""
        video = next(p for p in visible_pages(self.act.data, self.trip) if p["kind"] == "video")
        self.assertFalse(video["show_video"])
        self.assertEqual(video["title"], "How to make a roll")
        self.assertNotIn("atch", video["text"])

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
        # The lesson comes first in its module; the cards are its quick review.
        self.assertEqual([s for s, _ in slugs], ["sushi-lesson", "food-around-japan", "food-cards"])
        self.assertIsNone(slugs[0][1])
        self.assertIsNone(slugs[1][1])
        self.assertIsNotNone(slugs[2][1])


class EveryLessonIsWellFormed(TestCase):
    """Every lesson in the content: 10-20 pages, real pictures, game answers that can be tapped."""

    def test_every_lesson(self):
        call_command("load_content", verbosity=0)
        static = Path(settings.BASE_DIR) / "static" / "img"
        lessons = Activity.objects.filter(type="lesson")
        self.assertGreaterEqual(lessons.count(), 2)
        for act in lessons:
            data, name = act.data, act.slug
            pages = data["pages"]
            self.assertTrue(10 <= len(pages) <= 20, (name, len(pages)))
            kinds = [p["kind"] for p in pages]
            self.assertTrue(set(kinds) <= set(KINDS), name)
            if "video" in kinds:
                self.assertTrue(len(pages) // 4 <= kinds.index("video") <= 3 * len(pages) // 4, name)
                self.assertTrue(all(p.get("fallback") for p in pages if p["kind"] == "video"), name)
            pics = {p["id"] for p in data.get("pictures", [])}
            imgs = [p["img"] for p in data.get("pictures", [])] + [p["img"] for p in pages if p.get("img")]
            imgs += [c["img"] for p in pages for c in p.get("cards", [])]
            imgs += [p["img_he"] for p in data.get("pictures", []) + pages if p.get("img_he")]
            for img in imgs:
                self.assertTrue((static / img).exists(), (name, img))
            for p in pages:
                self.assertTrue(p.get("title_he"), (name, p["title"]))
                for r in p.get("rounds", []):
                    self.assertTrue(r.get("ask_he"), (name, r["ask"]))
                    if p["kind"] == "pick":
                        self.assertIn(r["answer"], r["choices"], name)
                        self.assertTrue(set(r["choices"]) <= pics, name)
                    else:
                        self.assertIn(r["answer"], p["belt"], name)
                for spot in p.get("spots", []):
                    self.assertTrue(0 <= spot["x"] <= 100 and 0 <= spot["y"] <= 100, name)
                    self.assertTrue(spot.get("text_he"), (name, spot["label"]))


class FlipBacksAreShort(TestCase):
    """T118: a flip card keeps the height of its longer side, so a long back text leaves the front half empty."""

    def test_every_flip_back_is_at_most_20_words(self):
        call_command("load_content", verbosity=0)
        for act in Activity.objects.filter(type="lesson"):
            for p in act.data["pages"]:
                for c in p.get("cards", []) if p["kind"] == "flip" else []:
                    self.assertLessEqual(len(c["text"].split()), 20, (act.slug, c["label"]))
                    self.assertLessEqual(len(c["text_he"].split()), 20, (act.slug, c["label"]))

class VideoPagesWithNoVideo(TestCase):
    """T107: in every lesson, a video page with no approved video says nothing about 'watch' or 'video'."""
    BANNED = ("watch", "video", "צפו", "צופים", "סרטון")

    def test_every_lesson_in_both_languages(self):
        call_command("load_content", verbosity=0)
        user = get_user_model().objects.create_user("v@example.com", "v@example.com")
        trip = Trip.objects.create(user=user, destination="japan")
        for age in (40, 5):
            Traveller.objects.create(trip=trip, age=age)
        lessons = [a for a in Activity.objects.filter(type="lesson") if any(p["kind"] == "video" for p in a.data["pages"])]
        self.assertGreaterEqual(len(lessons), 7)
        course = build_course(trip, sorted({a.module_id for a in lessons}))
        self.client.force_login(user)
        for act in lessons:
            item = course.items.get(activity=act)
            for lang in ("en", "he"):
                html = self.client.get(reverse("activity", args=[item.id]) + f"?lang={lang}").content.decode()
                start = html.index(">", html.index("lpage-video"))
                section = html[start:html.index("</section>", start)].lower()
                self.assertIn('class="ltext"', section, (act.slug, lang))
                for word in self.BANNED:
                    self.assertNotIn(word, section, (act.slug, lang, word))


class WordsLessonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("w@example.com", "w@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (40, 2):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.act = Activity.objects.get(module__slug="words", slug="words-lesson")
        course = build_course(cls.trip, [cls.act.module_id])
        cls.item = course.items.get(activity=cls.act)

    def page(self, lang="en"):
        self.client.force_login(self.user)
        r = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}")
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_every_kind_renders_in_english(self):
        html = self.page()
        self.assertEqual(html.count("data-page "), 14)
        for kind in KINDS:
            self.assertIn(f"lpage-{kind}", html)
        self.assertIn("Page 1 of 14", html)
        self.assertIn("In a Japanese shop", html)
        self.assertIn('data-spot="4"', html)               # 5 dots in the shop
        self.assertIn("irasshaimase", html)
        self.assertIn('data-plate="arigatou"', html)       # the word train
        self.assertIn("data-right", html)
        self.assertIn("gochisousama deshita", html)
        self.assertIn("audio/japan/irasshaimase.mp3", html)  # the spot word has a voice

    def test_hebrew(self):
        html = self.page("he")
        self.assertIn("מדברים כמו ילדים ביפן", html)
        self.assertIn("בחנות ביפן", html)
        self.assertIn("תפסו את \"אריגטו\", תודה!".replace('"', "&quot;"), html)
        self.assertIn("דף 1 מתוך 14", html)
        self.assertNotIn("In a Japanese shop", html)

    def test_unapproved_video_shows_the_written_lines_and_no_id(self):
        html = self.page()
        self.assertNotIn("4rY3y5VZcCg", html)
        self.assertIn("Say it slowly", html)
        self.assertIn("Clap once for each part", html)


class MannersLessonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("m@example.com", "m@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (38, 4):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.act = Activity.objects.get(module__slug="dos_donts", slug="manners-lesson")
        course = build_course(cls.trip, [cls.act.module_id])
        cls.item = course.items.get(activity=cls.act)

    def page(self, lang="en"):
        self.client.force_login(self.user)
        r = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}")
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_every_kind_renders_in_english(self):
        html = self.page()
        self.assertEqual(html.count("data-page "), 14)
        for kind in KINDS:
            self.assertIn(f"lpage-{kind}", html)
        self.assertIn("Page 1 of 14", html)
        self.assertIn("At the front door", html)
        self.assertIn("The toilet slippers", html)
        self.assertIn('data-spot="4"', html)               # 5 dots at the door, 5 at the shrine
        self.assertIn("temizuya", html)
        self.assertIn('data-plate="trashbag"', html)       # the manners train
        self.assertIn("data-right", html)
        self.assertIn("Osaka", html)
        self.assertIn("audio/japan/onsen.mp3", html)       # the page word has a voice
        self.assertIn("audio/japan/genkan.mp3", html)      # the spot word too

    def test_hebrew(self):
        html = self.page("he")
        self.assertIn("מנומסים כמו ילדים ביפן", html)
        self.assertIn("ליד דלת הכניסה", html)
        self.assertIn("נעלי השירותים", html)
        self.assertIn("דף 1 מתוך 14", html)
        self.assertNotIn("At the front door", html)

    def test_unapproved_video_shows_the_manners_game_and_no_id(self):
        html = self.page()
        self.assertNotIn("38JKwLfiMzA", html)
        self.assertNotIn("comes soon", html)
        self.assertIn("The manners game", html)
        self.assertIn("Shoe race", html)

    def test_facts_on_the_page(self):
        html = self.page()
        self.assertIn("5 yen coin", html)
        self.assertIn("stand on the left", html)
        self.assertIn("Slurping your noodles is fine", html)


class SafetyLessonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("s@example.com", "s@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (41, 5):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.act = Activity.objects.get(module__slug="safety", slug="safety-lesson")
        course = build_course(cls.trip, [cls.act.module_id])
        cls.item = course.items.get(activity=cls.act)

    def page(self, lang="en"):
        self.client.force_login(self.user)
        r = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}")
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_lesson_comes_first_and_the_cards_are_the_quick_review(self):
        slugs = list(self.item.course.items.order_by("order").values_list("activity__slug", "activity__title"))
        self.assertEqual(slugs[0][0], "safety-lesson")
        self.assertEqual(slugs[1], ("safety-intro", "Staying safe: quick review"))

    def test_every_kind_renders_in_english(self):
        html = self.page()
        self.assertEqual(html.count("data-page "), 14)
        for kind in KINDS:
            self.assertIn(f"lpage-{kind}", html)
        self.assertIn("Page 1 of 14", html)
        self.assertIn("Helpers on the street", html)
        self.assertIn('data-spot="4"', html)               # 5 dots on the street, 5 on the name card
        self.assertIn("maigo desu", html)
        self.assertIn('data-plate="staff"', html)          # the helper train
        self.assertIn("data-right", html)
        self.assertIn("audio/japan/koban.mp3", html)       # the spot word has a voice
        self.assertIn("audio/japan/jishin.mp3", html)      # the page word too

    def test_hebrew(self):
        html = self.page("he")
        self.assertIn("בטוחים כמו ילדים ביפן", html)
        self.assertIn("עוזרים ברחוב", html)
        self.assertIn("דף 1 מתוך 14", html)
        self.assertNotIn("Helpers on the street", html)

    def test_unapproved_video_shows_the_drill_and_no_id(self):
        html = self.page()
        self.assertNotIn("eML26rG3Ois", html)
        self.assertNotIn("comes soon", html)
        self.assertIn("The family safety drill", html)
        self.assertIn("Turtle time", html)

    def test_facts_on_the_page(self):
        html = self.page()
        self.assertIn("110 calls the police", html)
        self.assertIn("119 also calls the ambulance", html)
        self.assertIn("050-3816-2787", html)
        self.assertIn("drive on the LEFT", html)
        self.assertIn("Look right first", html)


class ChopsticksLessonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("c@example.com", "c@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (39, 4):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.act = Activity.objects.get(module__slug="chopsticks", slug="chopsticks-lesson")
        course = build_course(cls.trip, [cls.act.module_id])
        cls.item = course.items.get(activity=cls.act)

    def page(self, lang="en"):
        self.client.force_login(self.user)
        r = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}")
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_hebrew_page_shows_the_hebrew_picture(self):
        # T98: an explanation picture has a Hebrew twin; English pages keep the English picture.
        self.assertIn("lesson/chopsticks/asia_he.svg", self.page("he"))
        en = self.page("en")
        self.assertIn("lesson/chopsticks/asia.svg", en)
        self.assertNotIn("_he.svg", en)

    def test_lesson_comes_first_and_the_steps_are_the_quick_review(self):
        slugs = list(self.item.course.items.order_by("order").values_list("activity__slug", "activity__title"))
        self.assertEqual(slugs[0][0], "chopsticks-lesson")
        self.assertEqual(slugs[1], ("chopsticks-intro", "Eat with chopsticks: quick review"))

    def test_no_video_page_and_every_other_kind(self):
        # Michael, feedback T82: no video in the chopsticks lesson.
        kinds = [p["kind"] for p in self.act.data["pages"]]
        self.assertTrue(10 <= len(kinds) <= 20, len(kinds))
        self.assertNotIn("video", kinds)
        self.assertEqual(set(kinds), set(KINDS) - {"video"})

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
                self.assertTrue(set(p["belt"]) <= pics)

    def test_english(self):
        html = self.page()
        self.assertEqual(html.count("data-page "), 13)
        for kind in set(KINDS) - {"video"}:
            self.assertIn(f"lpage-{kind}", html)
        self.assertNotIn("lpage-video", html)
        self.assertNotIn("comes soon", html)
        self.assertIn("Page 1 of 13", html)
        self.assertIn("A hand with chopsticks", html)
        self.assertIn('data-spot="5"', html)               # 6 dots on the hand, 6 on the table
        self.assertIn('data-plate="onigiri"', html)        # the food train
        self.assertIn("data-right", html)
        self.assertIn("audio/japan/oshibori.mp3", html)    # the spot words have a voice
        self.assertIn("audio/japan/renge.mp3", html)       # a spot word too
        self.assertIn("never", html.lower())

    def test_kids_chopsticks_link_goes_through_the_click_counter(self):
        html = self.page()
        go = reverse("go", args=[self.item.id, "kids-chopsticks"])
        self.assertIn(go, html)
        r = self.client.get(go)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "https://www.aliexpress.com/item/1005007683787720.html")

    def test_hebrew(self):
        html = self.page("he")
        self.assertIn("אלופי הצ'ופסטיקס", html.replace("&#x27;", "'"))
        self.assertIn("דף 1 מתוך 13", html)
        self.assertIn("לצ'ופסטיקס לילדים", html.replace("&#x27;", "'"))
        self.assertNotIn("A hand with chopsticks", html)
        self.assertNotIn("Chopstick rules", html)


class StreetLessonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("v@example.com", "v@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (40, 6):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.act = Activity.objects.get(module__slug="streetview", slug="streetview-lesson")
        course = build_course(cls.trip, [cls.act.module_id])
        cls.item = course.items.get(activity=cls.act)

    def page(self, lang="en"):
        self.client.force_login(self.user)
        r = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}")
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_lesson_comes_first_and_the_three_hunts_follow(self):
        rows = list(self.item.course.items.order_by("order").values_list("activity__slug", "activity__type"))
        self.assertEqual(rows[0], ("streetview-lesson", "lesson"))
        self.assertEqual([t for _, t in rows[1:]], ["streetview"] * 3)

    def test_every_kind_and_a_video_slot_near_the_middle(self):
        kinds = [p["kind"] for p in self.act.data["pages"]]
        self.assertTrue(10 <= len(kinds) <= 20, len(kinds))
        self.assertEqual(set(kinds), set(KINDS))
        self.assertEqual(kinds.index("video"), len(kinds) // 2)
        video = next(p for p in self.act.data["pages"] if p["kind"] == "video")
        self.assertFalse(video["approved"])
        self.assertEqual(len(video["fallback"]), len(video["fallback_he"]))

    def test_every_picture_exists_and_every_game_answer_is_a_choice(self):
        data = self.act.data
        static = Path(settings.BASE_DIR) / "static" / "img"
        pics = {p["id"] for p in data["pictures"]}
        imgs = [p["img"] for p in data["pictures"]] + [p["img"] for p in data["pages"] if p.get("img")]
        imgs += [c["img"] for p in data["pages"] for c in p.get("cards", [])]
        for img in imgs:
            self.assertTrue((static / img).exists(), img)
        for p in data["pages"]:
            for r in p.get("rounds", []):
                self.assertIn(r["answer"], r.get("choices", p.get("belt")))
                self.assertTrue(set(r.get("choices", p.get("belt"))) <= pics)
            for spot in p.get("spots", []):
                self.assertTrue(0 < spot["x"] < 100 and 0 < spot["y"] < 100)

    def test_english(self):
        html = self.page()
        self.assertEqual(html.count("data-page "), 13)
        for kind in KINDS:
            self.assertIn(f"lpage-{kind}", html)
        self.assertNotIn("comes soon", html)
        self.assertIn("Page 1 of 13", html)
        self.assertIn("The five-thing walk", html)            # the video fallback
        self.assertNotIn("youtube.com/embed/QEC3MrWgnMU", html)  # not approved
        self.assertIn('data-plate="manhole"', html)
        self.assertIn("audio/japan/jidouhanbaiki.mp3", html)
        self.assertIn("A red label means the drink is HOT", html)

    def test_hebrew(self):
        html = self.page("he")
        self.assertIn("מה זה? דברים ברחוב ביפן", html)
        self.assertIn("דף 1 מתוך 13", html)
        self.assertIn("ההליכה של חמשת הדברים", html)
        self.assertNotIn("A street to explore", html)
        self.assertNotIn("The five-thing walk", html)


class TransportLessonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("t@example.com", "t@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (40, 5):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.act = Activity.objects.get(module__slug="transport", slug="transport-lesson")
        course = build_course(cls.trip, [cls.act.module_id])
        cls.item = course.items.get(activity=cls.act)

    def page(self, lang="en"):
        self.client.force_login(self.user)
        r = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}")
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_lesson_comes_first_and_the_cards_are_the_quick_review(self):
        rows = list(self.item.course.items.order_by("order").values_list("activity__slug", "activity__title"))
        self.assertEqual(rows[0][0], "transport-lesson")
        self.assertEqual(rows[1], ("transport-intro", "Getting around: quick review"))

    def test_every_kind_and_a_video_slot_near_the_middle(self):
        kinds = [p["kind"] for p in self.act.data["pages"]]
        self.assertTrue(10 <= len(kinds) <= 20, len(kinds))
        self.assertEqual(set(kinds), set(KINDS))
        self.assertLessEqual(abs(kinds.index("video") - len(kinds) // 2), 1)
        video = next(p for p in self.act.data["pages"] if p["kind"] == "video")
        self.assertFalse(video["approved"])
        self.assertEqual(len(video["fallback"]), len(video["fallback_he"]))

    def test_every_picture_exists_and_every_game_answer_is_a_choice(self):
        data = self.act.data
        static = Path(settings.BASE_DIR) / "static" / "img"
        pics = {p["id"] for p in data["pictures"]}
        imgs = [p["img"] for p in data["pictures"]] + [p["img"] for p in data["pages"] if p.get("img")]
        imgs += [c["img"] for p in data["pages"] for c in p.get("cards", [])]
        for img in imgs:
            self.assertTrue((static / img).exists(), img)
        for p in data["pages"]:
            for r in p.get("rounds", []):
                self.assertIn(r["answer"], r.get("choices", p.get("belt")))
                self.assertTrue(set(r.get("choices", p.get("belt"))) <= pics)
            for spot in p.get("spots", []):
                self.assertTrue(0 < spot["x"] < 100 and 0 < spot["y"] < 100)

    def test_fares_match_the_jr_rule(self):
        # Under 6 free with a paying adult, 6-11 half, a visitor of 12 pays the adult fare.
        fares = next(p for p in self.act.data["pages"] if p["title"] == "Who pays what?")
        self.assertEqual([r["answer"] for r in fares["rounds"]], ["free", "half", "adult"])

    def test_english(self):
        html = self.page()
        self.assertEqual(html.count("data-page "), 14)
        for kind in KINDS:
            self.assertIn(f"lpage-{kind}", html)
        self.assertNotIn("comes soon", html)
        self.assertIn("Page 1 of 14", html)
        self.assertIn("Four steps to board the Shinkansen", html)  # the video fallback
        self.assertNotIn("youtube.com/embed/9-kYEGjG92E", html)     # not approved
        self.assertIn('data-plate="shinkansen"', html)
        self.assertIn("audio/japan/kaisatsu.mp3", html)
        self.assertIn("the taxi is free", html)

    def test_hebrew(self):
        html = self.page("he")
        self.assertIn("נוסעים כמו מקומיים", html)
        self.assertIn("דף 1 מתוך 14", html)
        self.assertIn("ארבעה שלבים לעלות לשינקנסן", html)
        self.assertNotIn("In the station", html)
        self.assertNotIn("Four steps to board the Shinkansen", html)


class PackLessonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("p@example.com", "p@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (40, 5):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.act = Activity.objects.get(module__slug="buy_in_advance", slug="pack-lesson")
        course = build_course(cls.trip, [cls.act.module_id])
        cls.item = course.items.get(activity=cls.act)

    def page(self, lang="en"):
        self.client.force_login(self.user)
        r = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}")
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_lesson_comes_first_and_the_links_are_the_quick_review(self):
        rows = list(self.item.course.items.order_by("order").values_list("activity__slug", "activity__title"))
        self.assertEqual(rows[0][0], "pack-lesson")
        self.assertEqual(rows[1], ("buy_in_advance-intro", "Buy before you go: quick review"))

    def test_every_kind_and_a_video_slot_near_the_middle(self):
        kinds = [p["kind"] for p in self.act.data["pages"]]
        self.assertTrue(10 <= len(kinds) <= 20, len(kinds))
        self.assertEqual(set(kinds), set(KINDS))
        self.assertLessEqual(abs(kinds.index("video") - len(kinds) // 2), 1)
        video = next(p for p in self.act.data["pages"] if p["kind"] == "video")
        self.assertFalse(video["approved"])
        self.assertEqual(len(video["fallback"]), len(video["fallback_he"]))

    def test_every_picture_exists_and_every_game_answer_is_a_choice(self):
        data = self.act.data
        static = Path(settings.BASE_DIR) / "static" / "img"
        pics = {p["id"] for p in data["pictures"]}
        imgs = [p["img"] for p in data["pictures"]] + [p["img"] for p in data["pages"] if p.get("img")]
        imgs += [c["img"] for p in data["pages"] for c in p.get("cards", [])]
        for img in imgs:
            self.assertTrue((static / img).exists(), img)
        for p in data["pages"]:
            for r in p.get("rounds", []):
                self.assertIn(r["answer"], r.get("choices", p.get("belt")))
                self.assertTrue(set(r.get("choices", p.get("belt"))) <= pics)
            for spot in p.get("spots", []):
                self.assertTrue(0 < spot["x"] < 100 and 0 < spot["y"] < 100)

    def test_page_links_are_the_same_as_the_cards_and_go_through_the_click_hook(self):
        cards = {l["id"]: l["url"] for l in Activity.objects.get(slug="buy_in_advance-intro").data["links"]}
        links = [p["link"] for p in self.act.data["pages"] if p.get("link")]
        self.assertEqual({l["id"] for l in links}, {"visit-japan-web", "snack-box", "jr-pass"})
        for link in links:
            self.assertEqual(link["url"], cards[link["id"]])
        html = self.page()
        self.assertIn(reverse("go", args=[self.item.id, "visit-japan-web"]), html)
        self.assertNotIn("services.digital.go.jp", html)
        r = self.client.get(reverse("go", args=[self.item.id, "jr-pass"]))
        self.assertEqual(r["Location"], "https://japanrailpass.net/en/")

    def test_the_plug_is_type_a(self):
        plug = next(p for p in self.act.data["pages"] if p["title"] == "Which plug fits?")
        self.assertEqual(plug["rounds"][0]["answer"], "typea")

    def test_english(self):
        html = self.page()
        self.assertEqual(html.count("data-page "), 13)
        for kind in KINDS:
            self.assertIn(f"lpage-{kind}", html)
        self.assertNotIn("comes soon", html)
        self.assertIn("Page 1 of 13", html)
        self.assertIn("The packing list", html)                    # the video fallback
        self.assertNotIn("youtube.com/embed/q8nkH3lKmRg", html)    # not approved
        self.assertIn('data-plate="typea"', html)
        self.assertIn("audio/japan/hankachi.mp3", html)
        self.assertIn("two flat pins (type A), at 100 volts", html)

    def test_hebrew(self):
        html = self.page("he")
        self.assertIn("אורזים כמו מקצוענים", html)
        self.assertIn("דף 1 מתוך 13", html)
        self.assertIn("רשימת האריזה", html)
        self.assertNotIn("The open suitcase", html)
        self.assertNotIn("The packing list", html)


class FlipSayTests(TestCase):
    """T91: a flip card with a Japanese word says it on tap; a card without one stays silent."""
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("f@example.com", "f@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (40, 5):
            Traveller.objects.create(trip=cls.trip, age=age)

    def flips(self, module, slug):
        import re
        act = Activity.objects.get(module__slug=module, slug=slug)
        item = build_course(self.trip, [act.module_id]).items.get(activity=act)
        self.client.force_login(self.user)
        html = self.client.get(reverse("activity", args=[item.id]) + "?lang=en").content.decode()
        return re.findall(r'(<button type="button" class="flip"[^>]*>)\s*<span class="flip-front">(.*?)</span>\s*<span class="flip-back">', html, re.S)

    def test_sushi_flip_cards_say_their_word(self):
        cards = self.flips("food", "sushi-lesson")
        self.assertTrue(cards)
        for button, front in cards:
            has_word = 'lang="ja"' in front
            self.assertEqual(has_word, "data-say=" in button, button)
            if has_word:
                self.assertIn('data-say-src="/static/audio/japan/', button)
                self.assertIn("say-mark", front)
        nigiri = [b for b, f in cards if "nigiri" in b]
        self.assertTrue(nigiri, "no nigiri flip card")
        src = nigiri[0].split('data-say-src="')[1].split('"')[0]
        self.assertTrue(src.endswith("/nigiri.mp3"), src)
        self.assertTrue((Path(settings.BASE_DIR) / "static/audio/japan/nigiri.mp3").exists())

    def test_shrine_cards_name_the_place_they_say(self):
        """T119: the label over じんじゃ names the shrine, the label over おてら names the temple, and every card has a word and an mp3."""
        act = Activity.objects.get(module__slug="streetview", slug="streetview-lesson")
        page = next(p for p in act.data["pages"] if p.get("title") == "Shrine or temple?")
        by_reading = {c.get("reading"): c for c in page["cards"]}
        self.assertIn("Shrine", by_reading["jinja"]["label"])
        self.assertIn("שינטו", by_reading["jinja"]["label_he"])
        self.assertIn("Temple", by_reading["otera"]["label"])
        self.assertIn("בודהיסטי", by_reading["otera"]["label_he"])
        self.assertIn("incense", by_reading["joukouro"]["label"])
        for c in page["cards"]:
            self.assertTrue(c.get("japanese"), c["label"])
            self.assertTrue((Path(settings.BASE_DIR) / f"static/audio/japan/{c['reading']}.mp3").exists(), c["reading"])

    def test_card_without_a_word_is_silent(self):
        cards = self.flips("chopsticks", "chopsticks-lesson")
        silent = [b for b, f in cards if 'lang="ja"' not in f]
        self.assertTrue(silent)
        for button in silent:
            self.assertNotIn("data-say", button)


class HebrewPictureTwins(TestCase):
    """T98: a Hebrew twin of a lesson picture has no English explanation label left."""

    # Words that stay English on purpose: Japanese romaji and app names that families see in English.
    KEEP = {"maigo desu", "tasukete", "eSIM", "VJW", "IC"}

    def test_twins_have_no_english_labels(self):
        import re
        root = Path(settings.BASE_DIR) / "static" / "img" / "lesson"
        twins = sorted(root.rglob("*_he.svg"))
        self.assertGreaterEqual(len(twins), 6)
        for twin in twins:
            self.assertTrue(twin.with_name(twin.name.replace("_he.svg", ".svg")).exists(), twin)
            for label in re.findall(r"<text[^>]*>([^<]*)</text>", twin.read_text()):
                latin = " ".join(re.findall(r"[A-Za-z][A-Za-z.]*(?: [A-Za-z.]+)*", label))
                if latin:
                    self.assertIn(latin, self.KEEP, (twin.name, label))


class SushiPhotoTests(TestCase):
    """T159: every fish card in 'Fish and friends' has a real, credited, free-licence photo on its back."""
    FREE = {"CC0", "Public domain", "CC BY 2.0", "CC BY 3.0", "CC BY 4.0", "CC BY-SA 2.0", "CC BY-SA 3.0", "CC BY-SA 4.0"}

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("p@example.com", "p@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        Traveller.objects.create(trip=cls.trip, age=40)
        act = Activity.objects.get(module__slug="food", slug="sushi-lesson")
        cls.page = next(p for p in act.data["pages"] if p.get("title") == "Fish and friends")
        cls.item = build_course(cls.trip, [act.module_id]).items.get(activity=act)

    def test_every_photo_has_a_file_and_a_free_licence_credit(self):
        from content_admin.loader import load_photo_credits
        credits = load_photo_credits()
        self.assertEqual(len(self.page["cards"]), 6)
        for card in self.page["cards"]:
            self.assertTrue(card.get("photo"), card["label"])
            self.assertTrue((Path(settings.BASE_DIR) / "static/img" / card["photo"]).exists(), card["photo"])
            credit = credits[card["photo_credit"]]
            self.assertEqual(credit["file"], card["photo"])
            self.assertIn(credit["licence"], self.FREE)
            self.assertTrue(credit["author"] and credit["source_url"].startswith("https://commons.wikimedia.org/wiki/File:"))
        for credit in credits.values():
            self.assertTrue((Path(settings.BASE_DIR) / "static/img" / credit["file"]).exists(), credit["file"])

    def test_card_back_shows_the_photo_and_credit(self):
        self.client.force_login(self.user)
        for lang, word in (("en", "Photo:"), ("he", "צילום:")):
            html = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}").content.decode()
            self.assertEqual(html.count('class="flip-photo"'), 6, lang)
            self.assertEqual(html.count(f'<span class="photo-credit">{word} '), 6, lang)
            self.assertIn('/static/img/photo/sushi/sushi-maguro.jpg', html)
            self.assertIn(reverse("credits"), html)

    def test_credits_page_lists_every_photo(self):
        from content_admin.loader import load_photo_credits
        html = self.client.get(reverse("credits")).content.decode()
        for credit in load_photo_credits().values():
            self.assertIn(f'data-credit="{credit["id"]}"', html)
            self.assertIn(credit["source_url"], html)
            self.assertIn(credit["licence"], html)


class FoodAroundJapanTests(TestCase):
    """T160: one page per food, each with a real photo, a credit line, Hebrew text and a source."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("f@example.com", "f@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (38, 4):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.act = Activity.objects.get(module__slug="food", slug="food-around-japan")
        course = build_course(cls.trip, [cls.act.module_id])
        cls.item = course.items.get(activity=cls.act)

    def test_every_food_page_has_photo_credit_source_and_hebrew(self):
        from content_admin.loader import load_photo_credits
        credits = load_photo_credits()
        static = Path(settings.BASE_DIR) / "static" / "img"
        pages = self.act.data["pages"]
        food = [p for p in pages if p.get("photo_credit")]
        self.assertEqual(len(food), 9)
        for p in pages:
            self.assertTrue(p.get("source", "").startswith("https://"), p["title"])
        for p in food:
            self.assertTrue(p["img"].startswith("photo/food/"), p["title"])
            self.assertTrue((static / p["img"]).exists(), p["img"])
            self.assertIn(p["photo_credit"], credits)
            self.assertEqual(len(p["tips"]), len(p["tips_he"]), p["title"])
            self.assertTrue(p.get("text_he"), p["title"])

    def test_page_renders_in_both_languages(self):
        self.client.force_login(self.user)
        for lang, word in (("en", "Ramen around Japan"), ("he", "ראמן מסביב ליפן")):
            r = self.client.get(reverse("activity", args=[self.item.id]) + f"?lang={lang}")
            self.assertEqual(r.status_code, 200)
            html = r.content.decode()
            self.assertIn(word, html)
            self.assertEqual(html.count('class="lphoto-credit"'), 9, lang)
            self.assertIn("food-ekiben.jpg", html)
            self.assertNotIn("wikipedia.org", html)  # the source is for us, not shown


class WordsPicturesTests(TestCase):
    """T161: the words lesson pictures keep their size and their labels, and parse as SVG."""

    def test_every_words_picture_is_a_labelled_svg_of_the_old_size(self):
        import xml.etree.ElementTree as ET
        folder = Path(settings.BASE_DIR) / 'static' / 'img' / 'lesson' / 'words'
        names = sorted(p.stem for p in folder.glob('*.svg'))
        self.assertEqual(len(names), 12)
        for path in folder.glob('*.svg'):
            root = ET.parse(path).getroot()
            want = '0 0 400 260' if path.stem == 'shop' else '0 0 120 90'
            self.assertEqual(root.get('viewBox'), want, path.name)
            self.assertTrue(root.get('aria-label'), path.name)
            self.assertIsNotNone(root.find('{http://www.w3.org/2000/svg}title'), path.name)
