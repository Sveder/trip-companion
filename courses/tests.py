from django.conf import settings
import re
import tempfile
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from content_admin.models import Module
from activities.models import Clip
from courses.builder import build_course, reorder_course, suggestions
from courses.highlights import trip_phase
from courses.models import Course, CourseItem
from practice.models import PracticeItem
from trips.models import Traveller, Trip

# Card items after a lesson that bring new things, not a review of the lesson (T124).
NEW_CARDS = {"food-cards": ("More Japanese food", "עוד אוכל יפני")}


def make_trip(user, ages):
    trip = Trip.objects.create(user=user, destination="japan")
    for a in ages:
        Traveller.objects.create(trip=trip, age=a)
    return trip


class BuilderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("p@example.com", "p@example.com")

    def test_content_loads_every_japan_module(self):
        slugs = set(Module.objects.filter(country="japan").values_list("slug", flat=True))
        self.assertTrue({"food", "words", "dos_donts", "safety", "transport", "streetview", "chopsticks", "buy_in_advance"} <= slugs)

    def test_transport_child_fare_matches_jr_rule(self):
        # JR Central: the 12-year-old child fare is only for a Japanese elementary school, so visitors pay adult at 12.
        import yaml
        from django.conf import settings
        data = yaml.safe_load(open(settings.BASE_DIR / "content/japan/transport.yaml"))
        cards = next(a for a in data["activities"] if a["id"] == "transport-intro")["cards"]
        card = next(c for c in cards if c["title"] == "Children's fares")
        self.assertIn("From 12, they pay the adult fare.", card["text"])
        self.assertIn("Japanese elementary school", card["text"])
        self.assertIn("reserved seat", card["text"])

    def test_adults_only_child_modules_listed_but_off(self):
        rows = suggestions(make_trip(self.user, [40, 38]))
        child = [(m, on) for m, on in rows if m.audience == "child"]
        self.assertTrue(child, "child modules must stay in the list")
        self.assertFalse(any(on for _, on in child))
        self.assertTrue(all(on for m, on in rows if m.audience != "child"))

    def test_family_with_four_year_old_gets_child_modules(self):
        rows = suggestions(make_trip(self.user, [38, 36, 4]))
        self.assertTrue(all(on for m, on in rows if m.audience == "child"))

    def test_build_creates_ordered_items(self):
        trip = make_trip(self.user, [38, 36])
        ids = [m.id for m, on in suggestions(trip) if on]
        course = build_course(trip, ids)
        items = list(course.items.select_related("activity__module"))
        self.assertEqual([i.order for i in items], list(range(len(items))))
        orders = [i.activity.module.order for i in items]
        self.assertEqual(orders, sorted(orders))
        self.assertEqual(items[0].activity.module.slug, "food")

    def test_adults_only_course_keeps_module_order(self):
        trip = make_trip(self.user, [40, 38])
        ids = [m.id for m, _ in suggestions(trip)]  # every module, also the kids' ones
        items = list(build_course(trip, ids).items.select_related("activity__module"))
        keys = [
            (i.activity.module.order, i.activity.module.slug, i.activity.type != "lesson", i.activity.order, i.activity.slug)
            for i in items
        ]
        self.assertEqual(keys, sorted(keys))

    def test_lesson_comes_first_in_its_module_and_the_rest_is_a_quick_review(self):
        for ages in ([40, 38], [40, 38, 6, 2]):
            trip = make_trip(self.user, ages)
            ids = [m.id for m, on in suggestions(trip) if on]
            items = list(build_course(trip, ids).items.select_related("activity__module"))
            self.assertEqual(items[0].activity.type, "lesson", ages)
            seen = {}
            for i in items:
                seen.setdefault(i.activity.module.slug, []).append(i.activity)
            for slug, acts in seen.items():
                if not any(a.type == "lesson" for a in acts):
                    continue
                lessons = [n for n, a in enumerate(acts) if a.type == "lesson"]
                self.assertEqual(lessons, list(range(len(lessons))), slug)
                for a in acts[len(lessons):]:
                    if a.type == "streetview":
                        continue  # each hunt is its own place, not a review
                    if a.slug in NEW_CARDS:
                        # T124: these cards bring new things, so the title says what they hold.
                        self.assertEqual((a.title, a.data.get("title_he")), NEW_CARDS[a.slug], slug)
                        continue
                    self.assertEqual(a.title, f"{a.module.title}: quick review", slug)
                    self.assertEqual(a.data.get("title_he"), f"{a.module.title_he}: חזרה קצרה", slug)

    def test_reorder_keeps_item_ids_and_done_marks(self):
        trip = make_trip(self.user, [38, 4])
        ids = [m.id for m, on in suggestions(trip) if on]
        course = build_course(trip, ids)
        cards = course.items.get(activity__slug="food-cards")
        cards.mark_done()
        # An old course: the food cards first, the sushi lesson after them.
        lesson = course.items.get(activity__slug="sushi-lesson")
        cards_order, lesson_order = cards.order, lesson.order
        CourseItem.objects.filter(id=cards.id).update(order=lesson_order)
        CourseItem.objects.filter(id=lesson.id).update(order=cards_order)
        before = set(course.items.values_list("id", flat=True))
        self.assertTrue(reorder_course(course))
        self.assertFalse(reorder_course(course))
        self.assertEqual(set(course.items.values_list("id", flat=True)), before)
        self.assertEqual(course.items.first().activity.slug, "sushi-lesson")
        self.assertIsNotNone(CourseItem.objects.get(id=cards.id).done_at)

    def test_family_course_has_a_hunt_early_and_hunts_apart(self):
        trip = make_trip(self.user, [40, 38, 4, 2])
        ids = [m.id for m, on in suggestions(trip) if on]
        items = list(build_course(trip, ids).items.select_related("activity"))
        types = [i.activity.type for i in items]
        # The Street View lesson (T66) is the early kids' item; it shows what to look for, the hunts follow it.
        acts = [i.activity.slug for i in items]
        self.assertIn("streetview-lesson", acts[:4])  # right after the first module (food: 2 lessons + cards, T160)
        self.assertLess(acts.index("streetview-lesson"), types.index("streetview"))
        self.assertEqual(types.count("streetview"), 3)
        for a, b in zip(types, types[1:]):
            self.assertFalse(a == b == "streetview", types)
        slugs = [i.activity.module.slug for i in items]
        first_hunt = types.index("streetview")
        for adult in ("transport", "buy_in_advance"):
            self.assertGreater(slugs.index(adult), first_hunt)
        self.assertEqual(slugs[0], "food")

    def test_with_a_child_each_quick_review_follows_its_lesson(self):
        # T97: a kids' item goes only at a module edge, never between a lesson and its quick review.
        for ages in ([40, 38, 4, 2], [38, 4], [38, 9]):
            trip = make_trip(self.user, ages)
            ids = [m.id for m, on in suggestions(trip) if on]
            items = list(build_course(trip, ids).items.select_related("activity__module"))
            reviews = [
                n for n, i in enumerate(items)
                if i.activity.title.endswith(": quick review") or i.activity.slug in NEW_CARDS
            ]
            self.assertTrue(reviews, ages)
            for n in reviews:
                prev = items[n - 1].activity
                self.assertEqual(prev.module_id, items[n].activity.module_id, (ages, prev.slug))
                self.assertEqual(prev.type, "lesson", (ages, prev.slug))

    def test_rebuild_keeps_done_marks(self):
        trip = make_trip(self.user, [38, 4])
        ids = [m.id for m, on in suggestions(trip) if on]
        course = build_course(trip, ids)
        first = course.items.first()
        first.mark_done()
        course = build_course(trip, ids)
        self.assertIsNotNone(course.items.get(activity=first.activity).done_at)


class FlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def test_signin_by_email_code_then_setup_build_and_next(self):
        c = self.client
        self.assertContains(c.get("/"), "Uzbekistan")
        r = c.post(reverse("signin"), {"email": "Parent@Example.com"})
        self.assertRedirects(r, reverse("account_confirm_login_code"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        code = re.search(r"code is:\s+(\S+)", mail.outbox[0].body).group(1)
        r = c.post(reverse("account_confirm_login_code"), {"code": code})
        self.assertEqual(r.status_code, 302)
        # First visit: no trip yet -> trip setup.
        self.assertRedirects(c.get("/"), reverse("trip_setup"))
        # Michael's feedback: the step after setup is "choose your course", on the button and on the next page.
        self.assertContains(c.get(reverse("trip_setup")), "Next: choose your course")
        r = c.post(reverse("trip_setup"), {"destination": "japan", "grownup": 2, "kid": 1, "little": 1})
        self.assertRedirects(r, reverse("builder"))
        page = c.get(reverse("builder"))
        self.assertContains(page, "<span>Choose your course</span></h1>", html=False)
        self.assertContains(page, "Street View hunt")
        # T106: the server marks each card on or off, so an off card is grey before any script runs.
        cards = re.findall(r'<label class="card module ([^"]*)">\s*<input type="checkbox" name="modules" value="\d+" ?(checked)?', page.content.decode())
        self.assertTrue(cards)
        for cls, checked in cards:
            self.assertIn("on" if checked else "off", cls.split())
        # Parent adds "buy before you go" on top of the suggestion (it is suggested anyway here).
        ids = [str(m.id) for m in Module.objects.all()]
        r = c.post(reverse("builder"), {"modules": ids})
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)
        course = Course.objects.get()
        first = course.items.first()
        r = c.get(reverse("next_step"))
        self.assertRedirects(r, reverse("activity", args=[first.id]))
        page = c.get(reverse("activity", args=[first.id]))
        self.assertContains(page, "Sushi")
        # Marking it done shows the praise screen; its Next button goes home, which opens the next activity.
        r = c.post(reverse("activity_done", args=[first.id]))
        self.assertRedirects(r, reverse("activity_praise", args=[first.id]), fetch_redirect_response=False)
        praise = c.get(r["Location"])
        self.assertContains(praise, "Great job!")
        self.assertContains(praise, 'href="/"')
        second = course.items.all()[1]
        self.assertRedirects(c.get(reverse("next_step")), reverse("activity", args=[second.id]))

    def test_other_users_activity_is_404(self):
        a = get_user_model().objects.create_user("a@example.com", "a@example.com")
        b = get_user_model().objects.create_user("b@example.com", "b@example.com")
        trip = make_trip(a, [30])
        course = build_course(trip, [m.id for m in Module.objects.all()])
        self.client.force_login(b)
        r = self.client.get(reverse("activity", args=[course.items.first().id]))
        self.assertEqual(r.status_code, 404)

    def test_builder_marks_a_switched_off_card_off(self):
        # T106: a module the family switched off gets the 'off' class (grey border), the others 'on'.
        u = get_user_model().objects.create_user("t106@example.com", "t106@example.com")
        trip = make_trip(u, [35, 6])
        food = Module.objects.get(slug="food")
        build_course(trip, [food.id])
        self.client.force_login(u)
        html = self.client.get(reverse("builder")).content.decode()
        cards = re.findall(r'<label class="card module ([^"]*)">\s*<input type="checkbox" name="modules" value="(\d+)"', html)
        self.assertEqual(len(cards), Module.objects.filter(country="japan").count())
        for cls, mid in cards:
            self.assertIn("on" if int(mid) == food.id else "off", cls.split())

    def test_bad_ages_rejected(self):
        u = get_user_model().objects.create_user("c@example.com", "c@example.com")
        self.client.force_login(u)
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "kid": "two"})
        self.assertContains(r, "Enter a whole number")
        r = self.client.post(reverse("trip_setup"), {"destination": "japan"})
        self.assertContains(r, "Put at least one person on the plane.")


class ThemeTests(TestCase):
    """Slice 3: every page wears the theme; the finish page celebrates."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("t@example.com", "t@example.com")

    def test_welcome_shows_the_neutral_mark_and_loads_theme(self):
        html = self.client.get("/").content.decode()
        self.assertIn('class="guide mark hero-guide"', html)  # T87: the welcome page is app-wide, no deer
        self.assertIn("css/app.css", html)
        self.assertIn("js/celebrate.js", html)

    def test_welcome_ready_country_card_links_to_trip_setup(self):
        html = self.client.get("/").content.decode()
        self.assertRegex(html, r'<a class="card country go" href="/trip/\?destination=japan"')
        self.assertNotRegex(html, r'<a class="card country soon')

    def test_header_mark_is_decorative(self):
        html = self.client.get("/").content.decode()
        self.assertRegex(html, r'class="guide mark small"[^>]*aria-hidden="true"')

    def test_finish_page_celebrates(self):
        trip = make_trip(self.user, [38, 4])
        course = build_course(trip, [m.id for m, on in suggestions(trip) if on])
        for item in course.items.all():
            item.mark_done()
        self.client.force_login(self.user)
        html = self.client.get("/").content.decode()
        self.assertIn("You did every activity!", html)
        self.assertRegex(html, r"<body[^>]*data-celebrate")
        self.assertIn("data-celebrate-again", html)
        self.assertIn("hero-guide cheer", html)


CLIP_DIR = tempfile.mkdtemp(prefix="trip-clips-")


@override_settings(CLIP_ROOT=CLIP_DIR)
class AfterTheTripTests(TestCase):
    """Slice 9: home by trip date: before and during = the course, after = the highlights."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.user = get_user_model().objects.create_user("h@example.com", "h@example.com")
        self.trip = make_trip(self.user, [38, 4])
        self.course = build_course(self.trip, [m.id for m, on in suggestions(self.trip) if on])
        self.client.force_login(self.user)

    def set_dates(self, start_in, end_in):
        today = timezone.localdate()
        self.trip.start_date = today + timedelta(days=start_in)
        self.trip.end_date = today + timedelta(days=end_in)
        self.trip.save()

    def finish_all(self):
        for item in self.course.items.all():
            item.mark_done()

    def test_phase_by_date(self):
        today = date(2026, 11, 10)
        trip = Trip(start_date=date(2026, 11, 10), end_date=date(2026, 11, 20))
        self.assertEqual(trip_phase(trip, date(2026, 11, 9)), "before")
        self.assertEqual(trip_phase(trip, today), "during")
        self.assertEqual(trip_phase(trip, date(2026, 11, 20)), "during")
        self.assertEqual(trip_phase(trip, date(2026, 11, 21)), "after")
        self.assertEqual(trip_phase(Trip(), date(2030, 1, 1)), "before")

    def test_before_the_trip_home_offers_the_course_and_next_opens_the_next_activity(self):
        self.set_dates(10, 20)
        r = self.client.get("/")
        self.assertTemplateUsed(r, "courses/welcome.html")
        self.assertContains(r, reverse("course"))
        r = self.client.get(reverse("next_step"))
        self.assertRedirects(r, reverse("activity", args=[self.course.next_item().id]), fetch_redirect_response=False)

    def test_before_the_trip_finished_course_offers_the_quiz(self):
        self.set_dates(10, 20)
        self.finish_all()
        html = self.client.get("/").content.decode()
        self.assertIn("You did every activity!", html)
        self.assertIn("Play the quiz every day until the trip", html)
        self.assertIn(reverse("quiz"), html)
        self.assertNotIn("Welcome back from Japan", html)

    def test_during_the_trip_home_keeps_the_course(self):
        self.set_dates(-2, 5)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.finish_all()
        html = self.client.get("/").content.decode()
        self.assertIn("You are in Japan now!", html)
        self.assertNotIn("Welcome back from Japan", html)

    def test_after_the_trip_home_shows_highlights(self):
        self.set_dates(-20, -1)
        items = list(self.course.items.select_related("activity__module"))
        food = items[0]
        food.mark_done()
        words_item = next(i for i in items if i.activity.type == "words")
        self.client.post(reverse("activity_done", args=[words_item.id]))
        konnichiwa = PracticeItem.objects.get(trip=self.trip, key__endswith="/konnichiwa")
        konnichiwa.answer(True)
        Clip.objects.create(trip=self.trip, item=food, file=SimpleUploadedFile("c.webm", b"x"), content_type="video/webm", size=1)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Welcome back from Japan!", html)
        self.assertIn(food.activity.title, html)
        self.assertIn(escape(words_item.activity.title), html)
        self.assertEqual(len(r.context["done"]), 2)
        self.assertEqual(len(r.context["clips"]), 1)
        self.assertIn(reverse("clip", args=[r.context["clips"][0].id]), html)
        self.assertIn("konnichiwa ⭐", html)
        self.assertIn("arigatou", html)
        known = [w["entry"]["reading"] for w in r.context["words"] if w["known"]]
        self.assertEqual(known, ["konnichiwa"])

    def test_highlights_say_words_we_met_not_learned(self):
        """T39: a family that got 1 of 8 right did not learn every word."""
        self.set_dates(-20, -1)
        words_item = next(i for i in self.course.items.select_related("activity__module") if i.activity.type == "words")
        self.client.post(reverse("activity_done", args=[words_item.id]))
        PracticeItem.objects.get(trip=self.trip, key__endswith="/konnichiwa").answer(True)
        html = self.client.get(reverse("highlights")).content.decode()
        self.assertIn("Words we met", html)
        self.assertNotIn("Words we learned", html)
        self.assertIn('class="cards word-grid"', html)
        self.assertEqual(html.count("⭐</h3>"), 1)

    def lesson(self, module, slug):
        from content_admin.models import Activity
        return Activity.objects.select_related("module").get(module__country=self.trip.destination, module__slug=module, slug=slug)

    def test_highlights_count_lesson_words(self):
        """T112: a finished sushi lesson and no words module still fills 'Words we met', one card per word."""
        from courses.highlights import highlights
        from practice.items import add_items, due_items
        self.set_dates(-20, -1)
        add_items(self.trip, self.lesson("food", "sushi-lesson"))
        add_items(self.trip, self.lesson("food", "sushi-lesson"))
        words = highlights(self.trip, self.course)["words"]
        japanese = [w["entry"]["japanese"] for w in words]
        self.assertGreaterEqual(len(words), 5)
        self.assertEqual(len(japanese), len(set(japanese)))
        self.assertIn("ネタ", japanese)
        neta = next(w["entry"] for w in words if w["entry"]["japanese"] == "ネタ")
        self.assertEqual(neta["meaning"], "Fish")
        # A flip card whose label only repeats the reading takes its own meaning (T134), or the label of the same word on another page.
        nigiri = next(w["entry"] for w in words if w["entry"]["japanese"] == "にぎり")
        self.assertEqual(nigiri["meaning"], "rice with a topping")
        by_reading = {w["entry"]["reading"]: w["entry"]["meaning"] for w in words}
        for reading, meaning in [("maguro", "Tuna"), ("ebi", "Shrimp"), ("saamon", "Salmon")]:
            if reading in by_reading:
                self.assertEqual(by_reading[reading], meaning)
        self.assertTrue(all(by_reading.values()), by_reading)
        html = self.client.get(reverse("highlights")).content.decode()
        self.assertNotIn("No words yet", html)
        self.assertIn("ネタ", html)
        # Advisor bug 3 (fixed by T92): the finished lesson gives the quiz something to ask.
        self.assertTrue(due_items(self.trip, timezone.localdate()))

    def test_highlights_words_lesson_shows_real_meanings(self):
        """T134: a family that did only the words lesson sees 'thank you' / 'תודה', not a label or a transliteration."""
        from courses.highlights import highlights
        from practice.items import add_items
        self.set_dates(-20, -1)
        add_items(self.trip, self.lesson("words", "words-lesson"))
        words = {w["entry"]["reading"]: w["entry"]["meaning"] for w in highlights(self.trip, self.course)["words"]}
        self.assertEqual(words["arigatou"], "thank you")
        self.assertEqual(words["ohayou"], "good morning")
        self.assertEqual(words["irasshaimase"], "welcome!")
        self.assertEqual(words["atatamemasu ka"], "shall I warm it up?")
        self.assertNotIn("The shop worker", words.values())
        self.assertTrue(all(words.values()), words)
        html = self.client.get(reverse("highlights")).content.decode()
        self.assertIn("thank you", html)
        html = self.client.get(reverse("highlights") + "?lang=he").content.decode()
        self.assertIn('<p class="meaning">תודה</p>', html)
        self.assertIn('<p class="meaning">בוקר טוב</p>', html)
        self.assertNotIn('<p class="meaning">אריגטו</p>', html)
        self.assertNotIn("העובד בחנות</p>", html)

    def test_highlights_list_words_module_first(self):
        """T112: lesson words come after the words module, and the list stops at WORDS_MAX."""
        from courses.highlights import WORDS_MAX, highlights
        from practice.items import add_items
        self.set_dates(-20, -1)
        add_items(self.trip, self.lesson("food", "sushi-lesson"))
        add_items(self.trip, self.lesson("words", "words-intro"))
        for module, slug in [("streetview", "streetview-lesson"), ("transport", "transport-lesson"), ("safety", "safety-lesson")]:
            add_items(self.trip, self.lesson(module, slug))
        words = highlights(self.trip, self.course)["words"]
        self.assertEqual(words[0]["entry"]["reading"], "konnichiwa")
        self.assertNotEqual(words[-1]["entry"]["reading"], "konnichiwa")
        self.assertLessEqual(len(words), WORDS_MAX)
        self.client.cookies["lang"] = "he"
        html = self.client.get(reverse("highlights") + "?lang=he").content.decode()
        self.assertIn("דג", html)

    def test_word_grid_keeps_japanese_on_one_line(self):
        """T41: いただきます must not break in the middle of the word in the 2-column grid."""
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static/css/app.css").read_text()
        rule = re.search(r"\.cards\.word-grid \.jp\.small \{([^}]*)\}", css)
        self.assertIsNotNone(rule)
        self.assertIn("white-space: nowrap", rule.group(1))

    def test_word_grid_column_fits_the_longest_word(self):
        """T120: a desktop word card is wide enough for an 8-kana word plus an emoji (about 172 px)."""
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static/css/app.css").read_text()
        rule = re.search(r"\.cards\.word-grid \{ grid-template-columns: repeat\(auto-fit, minmax\((\d+)px", css)
        self.assertIsNotNone(rule)
        self.assertGreaterEqual(int(rule.group(1)), 190)

    def test_course_list_is_a_grid_on_desktop_and_tv(self):
        """T139: the course page has 2 cards per row on a desktop and 3 on the TV, not one long column."""
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static/css/app.css").read_text()
        self.assertRegex(css, r"@media \(min-width: 900px\) \{ \.course-list \{ grid-template-columns: repeat\(2,")
        self.assertRegex(css, r"\.tv \.course-list \{ grid-template-columns: repeat\(3,")

    def test_after_the_trip_with_nothing_done(self):
        self.set_dates(-20, -1)
        html = self.client.get("/").content.decode()
        self.assertIn("Welcome back from Japan!", html)
        self.assertIn("No activities yet", html)
        self.assertIn("No words yet", html)

    def test_highlights_hide_coming_soon_stubs(self):
        self.set_dates(-20, -1)
        stub = self.course.items.select_related("activity__module").last()
        Module.objects.filter(id=stub.activity.module_id).update(ready=False)
        stub.mark_done()
        r = self.client.get("/")
        self.assertNotIn(stub, r.context["done"])

    def test_other_family_clips_stay_out(self):
        self.set_dates(-20, -1)
        other = get_user_model().objects.create_user("o@example.com", "o@example.com")
        other_trip = make_trip(other, [40])
        Clip.objects.create(trip=other_trip, file=SimpleUploadedFile("c.webm", b"x"), content_type="video/webm", size=1)
        r = self.client.get("/")
        self.assertEqual(r.context["clips"], [])

    def test_highlights_page_works_before_the_trip(self):
        self.set_dates(10, 20)
        r = self.client.get(reverse("highlights"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertNotIn("Welcome back", html)
        self.assertIn("Look at everything you did to get ready for Japan!", html)
        self.assertNotIn("next trip", html)

    def test_highlights_page_during_the_trip_has_no_welcome_back(self):
        self.set_dates(-2, 5)
        html = self.client.get(reverse("highlights")).content.decode()
        self.assertNotIn("Welcome back", html)

    def test_highlights_done_date_sits_in_a_nowrap_span(self):
        # T140: on a desktop card the date broke in two ('· 9' / 'Oct').
        self.set_dates(10, 20)
        item = self.course.items.select_related("activity__module").filter(activity__module__ready=True).first()
        item.mark_done()
        html = self.client.get(reverse("highlights")).content.decode()
        self.assertIn('<span class="hl-date">', html)
        self.assertNotIn('· <span class="hl-date">', html)
        css = (settings.BASE_DIR / "static/css/app.css").read_text()
        self.assertIn(".hl-date { display: block; white-space: nowrap; }", css)

    def test_highlights_page_after_the_trip_says_welcome_back(self):
        self.set_dates(-20, -1)
        html = self.client.get(reverse("highlights")).content.decode()
        self.assertIn("Welcome back from Japan!", html)


class StubTests(TestCase):
    """A "coming soon" stub cannot be marked done, and the course goes past it."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.user = get_user_model().objects.create_user("s@example.com", "s@example.com")
        self.trip = make_trip(self.user, [38, 4])
        self.course = build_course(self.trip, [m.id for m in Module.objects.all()])
        food = Module.objects.get(slug="food")
        Module.objects.exclude(id=food.id).update(ready=False)
        self.ready = list(self.course.ready_items())
        self.stubs = [i for i in self.course.items.select_related("activity__module") if i.is_stub]
        self.client.force_login(self.user)

    def test_stub_cannot_be_marked_done(self):
        stub = self.stubs[0]
        self.client.post(reverse("activity_done", args=[stub.id]))
        stub.refresh_from_db()
        self.assertIsNone(stub.done_at)
        page = self.client.get(reverse("activity", args=[stub.id]))
        self.assertContains(page, "coming soon")
        self.assertNotContains(page, "We did it!")

    def test_finish_after_the_ready_items_only(self):
        self.assertTrue(self.ready and self.stubs)
        for item in self.ready:
            self.assertRedirects(self.client.get(reverse("next_step")), reverse("activity", args=[item.id]))
            page = self.client.get(reverse("activity", args=[item.id]))
            self.assertEqual(page.context["progress"]["total"], len(self.ready))
            self.client.post(reverse("activity_done", args=[item.id]))
        page = self.client.get("/")
        self.assertTemplateUsed(page, "courses/finished.html")
        self.assertContains(page, "More activities come soon")

    def test_stub_that_turns_ready_is_not_done(self):
        stub = self.stubs[0]
        self.client.post(reverse("activity_done", args=[stub.id]))
        for item in self.ready:
            self.client.post(reverse("activity_done", args=[item.id]))
        Module.objects.filter(id=stub.activity.module_id).update(ready=True)
        stub.refresh_from_db()
        self.assertIsNone(stub.done_at)
        self.assertRedirects(self.client.get(reverse("next_step")), reverse("activity", args=[stub.id]))

    def test_admin_ready_switch_clears_old_done_marks(self):
        from django.contrib.admin.sites import site
        from content_admin.admin import ModuleAdmin

        stub = self.stubs[0]
        stub.mark_done()  # done before this fix existed
        module = Module.objects.get(id=stub.activity.module_id)
        module.ready = True
        form = type("F", (), {"changed_data": ["ready"]})()
        ModuleAdmin(Module, site).save_model(None, module, form, True)
        stub.refresh_from_db()
        self.assertIsNone(stub.done_at)


class PraiseTests(TestCase):
    """'We did it!' shows 'Great job!' and a progress bar that moves, then Next opens the next activity."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.user = get_user_model().objects.create_user("p@example.com", "p@example.com")
        self.trip = make_trip(self.user, [38, 4])
        self.course = build_course(self.trip, [m.id for m in Module.objects.all()])
        self.ready = list(self.course.ready_items())
        self.client.force_login(self.user)

    def test_praise_after_the_first_activity(self):
        first = self.ready[0]
        r = self.client.post(reverse("activity_done", args=[first.id]))
        self.assertRedirects(r, reverse("activity_praise", args=[first.id]), fetch_redirect_response=False)
        page = self.client.get(r["Location"])
        self.assertTemplateUsed(page, "activities/praise.html")
        self.assertContains(page, "Great job!")
        self.assertContains(page, f"1 of {len(self.ready)} done")
        self.assertEqual(page.context["progress"]["before"], 0)
        self.assertRedirects(self.client.get(reverse("next_step")), reverse("activity", args=[self.ready[1].id]))
        # T108: the emoji is a badge beside the guide, and a 'Next up' card names the next activity.
        self.assertContains(page, 'class="praise-top"')
        self.assertContains(page, "Next up")
        self.assertContains(page, self.ready[1].activity.local_title)

    def test_praise_before_done_goes_to_the_activity(self):
        first = self.ready[0]
        r = self.client.get(reverse("activity_praise", args=[first.id]))
        self.assertRedirects(r, reverse("activity", args=[first.id]))

    def test_no_praise_for_an_activity_done_before(self):
        first = self.ready[0]
        self.client.post(reverse("activity_done", args=[first.id]))
        r = self.client.post(reverse("activity_done", args=[first.id]))
        self.assertRedirects(r, reverse("activity", args=[self.ready[1].id]), fetch_redirect_response=False)

    def test_next_goes_after_the_activity_picked_on_the_course_page(self):
        # Earlier ones done, three left open; the family picks a later one on the course page.
        self.assertGreaterEqual(len(self.ready), 10)
        for item in self.ready[:5]:
            item.mark_done()
        # A hunt adds ?found=N to its praise link, so pick a later item that is not a hunt.
        n = next(n for n in range(8, len(self.ready) - 1) if self.ready[n].activity.type != "streetview")
        picked, after = self.ready[n], self.ready[n + 1]
        r = self.client.post(reverse("activity_done", args=[picked.id]), {"skip": "1"})
        self.assertRedirects(r, reverse("activity_praise", args=[picked.id]), fetch_redirect_response=False)
        page = self.client.get(reverse("activity_praise", args=[picked.id]))
        self.assertContains(page, f'href="{reverse("activity", args=[after.id])}"')
        # Done again from the course page: no praise, straight to the next one after it.
        r = self.client.post(reverse("activity_done", args=[picked.id]))
        self.assertRedirects(r, reverse("activity", args=[after.id]), fetch_redirect_response=False)
        # The last one wraps to the first unfinished: activity 6 (index 5).
        last = self.ready[-1]
        self.client.post(reverse("activity_done", args=[last.id]), {"skip": "1"})
        page = self.client.get(reverse("activity_praise", args=[last.id]))
        self.assertContains(page, f'href="{reverse("activity", args=[self.ready[5].id])}"')

    def test_last_activity_goes_to_the_finish_page(self):
        for item in self.ready[:-1]:
            found = [str(i) for i in range(len(item.activity.data.get("spots", [])))]
            self.client.post(reverse("activity_done", args=[item.id]), {"found": found})
        last = self.ready[-1]
        found = [str(i) for i in range(len(last.activity.data.get("spots", [])))]
        r = self.client.post(reverse("activity_done", args=[last.id]), {"found": found})
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)

    def test_other_users_praise_is_404(self):
        other = get_user_model().objects.create_user("o@example.com", "o@example.com")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("activity_praise", args=[self.ready[0].id])).status_code, 404)


class CoursePageTests(TestCase):
    """The course page lists every activity in order, and a done one opens again."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.user = get_user_model().objects.create_user("c@example.com", "c@example.com")
        self.trip = make_trip(self.user, [38, 4])
        self.course = build_course(self.trip, [m.id for m in Module.objects.all()])
        self.client.force_login(self.user)

    def test_nav_our_course_opens_the_course_page(self):
        page = self.client.get(reverse("course"))
        self.assertContains(page, f'href="{reverse("course")}">Our course')
        self.assertContains(page, f'href="{reverse("builder")}"')
        self.assertContains(page, "Change our course")

    def test_lists_items_in_order_with_done_marks(self):
        items = list(self.course.ready_items())
        items[0].mark_done()
        page = self.client.get(reverse("course"))
        html = page.content.decode()
        positions = [html.index(reverse("activity", args=[i.id])) for i in items]
        self.assertEqual(positions, sorted(positions))
        self.assertContains(page, "✓ Done", count=1)
        self.assertEqual(page.context["next_id"], items[1].id)

    def test_after_everything_is_done_food_opens_again(self):
        for item in self.course.ready_items().select_related("activity"):
            found = [str(i) for i in range(len(item.activity.data.get("spots", [])))]
            self.client.post(reverse("activity_done", args=[item.id]), {"found": found})
        self.assertTemplateUsed(self.client.get("/"), "courses/finished.html")
        food = self.course.items.filter(activity__module__slug="food").first()
        page = self.client.get(reverse("course"))
        self.assertContains(page, reverse("activity", args=[food.id]))
        self.assertContains(page, food.activity.module.title)
        again = self.client.get(reverse("activity", args=[food.id]))
        self.assertEqual(again.status_code, 200)
        self.assertTemplateUsed(again, f"activities/{food.activity.type}.html")

    def _finish_all(self, skip_hunts=False):
        hunts = []
        for item in self.course.ready_items().select_related("activity"):
            if skip_hunts and item.activity.type == "streetview":
                self.client.post(reverse("activity_done", args=[item.id]), {"skip": "1"})
                hunts.append(item)
            else:
                found = [str(i) for i in range(len(item.activity.data.get("spots", [])))]
                self.client.post(reverse("activity_done", args=[item.id]), {"found": found})
        return hunts

    def test_a_hunt_skipped_with_none_found_is_not_done(self):
        # T121: found 0 shows 'Skipped' and 'Play again', and does not count in 'We did N of M'.
        hunts = self._finish_all(skip_hunts=True)
        self.assertTrue(hunts)
        total = self.course.ready_items().count()
        page = self.client.get(reverse("course"))
        self.assertEqual(page.context["done"], total - len(hunts))
        self.assertContains(page, f"We did {total - len(hunts)} of {total}.")
        self.assertContains(page, "Skipped", count=len(hunts))
        self.assertContains(page, "✓ Done", count=total - len(hunts))
        self.assertContains(page, "Play again", count=len(hunts))
        # The course goes past the hunts, but the end page is no every-activity party.
        home = self.client.get("/")
        self.assertTemplateUsed(home, "courses/finished.html")
        self.assertNotContains(home, "You did every activity!")
        self.assertContains(home, f"{len(hunts)} hunts are still waiting")
        self.client.post(reverse("set_language"), {"language": "he", "next": "/"})
        self.assertContains(self.client.get(reverse("course")), "דילגנו", count=len(hunts))
        self.assertNotContains(self.client.get("/"), "עשיתם את כל הפעילויות!")

    def test_a_hunt_with_one_found_stays_done(self):
        self._finish_all()
        hunt = self.course.ready_items().filter(activity__type="streetview").first()
        hunt.found = 1
        hunt.save(update_fields=["found"])
        total = self.course.ready_items().count()
        page = self.client.get(reverse("course"))
        self.assertEqual(page.context["done"], total)
        self.assertNotContains(page, "Skipped")
        self.assertContains(page, "✓ Done", count=total)
        self.assertContains(self.client.get("/"), "You did every activity!")

    def test_every_item_shows_its_module_name_in_en_and_he(self):
        items = list(self.course.items.select_related("activity__module"))
        for lang, field in (("en", "title"), ("he", "title_he")):
            self.client.post(reverse("set_language"), {"language": lang, "next": "/"})
            html = self.client.get(reverse("course")).content.decode()
            rows = re.findall(r"<li>(.*?)</li>", html, re.S)
            self.assertEqual(len(rows), len(items), lang)
            for row, item in zip(rows, items):
                module = getattr(item.activity.module, field) or item.activity.module.title
                self.assertIn(f"<small>{escape(module)}</small>", row, (lang, item.activity.slug))

    def test_no_course_yet_goes_to_the_builder(self):
        self.course.delete()
        self.assertRedirects(self.client.get(reverse("course")), reverse("builder"))


class JapanFlagTests(TestCase):
    """Feedback T86: the Japan card shows a drawn Hinomaru (white field, red disc #bc002d), not the flag emoji."""

    def test_svg_is_a_hinomaru(self):
        from django.conf import settings
        svg = (settings.BASE_DIR / "static" / "img" / "flags" / "japan.svg").read_text()
        self.assertIn('viewBox="0 0 900 600"', svg)  # 2:3
        self.assertIn('fill="#ffffff"', svg)
        self.assertIn('<circle cx="450" cy="300" r="180" fill="#bc002d"/>', svg)  # disc is 3/5 of the height, centred

    def test_welcome_and_setup_use_the_svg(self):
        page = self.client.get(reverse("home")).content.decode()
        self.assertIn("img/flags/japan.svg", page)
        self.assertNotIn("🇯🇵", page)
        user = get_user_model().objects.create_user("flag@example.com", "flag@example.com", "x")
        self.client.force_login(user)
        page = self.client.get(reverse("trip_setup")).content.decode()
        self.assertIn("img/flags/japan.svg", page)
        self.assertNotIn("🇯🇵", page)



class UzbekistanFlagTests(TestCase):
    """T90: the Uzbekistan 'coming soon' card shows a drawn flag (1:2, blue/white/green with red lines), not the emoji."""

    def test_svg_is_the_flag(self):
        from django.conf import settings
        svg = (settings.BASE_DIR / "static" / "img" / "flags" / "uzbekistan.svg").read_text()
        self.assertIn('viewBox="0 0 500 250"', svg)  # 1:2
        for colour in ("#0099b5", "#ffffff", "#1eb53a", "#ce1126"):
            self.assertIn(colour, svg)
        self.assertEqual(svg.count('<use href="#s"'), 12)  # stars in rows of 3, 4 and 5

    def test_welcome_and_setup_use_the_svg(self):
        page = self.client.get(reverse("home")).content.decode()
        self.assertIn("img/flags/uzbekistan.svg", page)
        self.assertNotIn("🇺🇿", page)
        user = get_user_model().objects.create_user("uzflag@example.com", "uzflag@example.com", "x")
        self.client.force_login(user)
        page = self.client.get(reverse("trip_setup")).content.decode()
        self.assertIn("img/flags/uzbekistan.svg", page)
        self.assertNotIn("🇺🇿", page)

class ComingSoonCardsTests(TestCase):
    """T146: Japan, Uzbekistan (T171), four coming-soon places and a 'Request a new one' mail card on the welcome page."""

    def test_welcome_has_seven_cards_and_the_request_mail_link(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertEqual(html.count('class="card country go"'), 2)  # Japan, and Uzbekistan since T171
        self.assertEqual(html.count('class="card country soon"'), 4)
        self.assertIn('?destination=uzbekistan"', html)
        self.assertEqual(html.count('class="card country go request"'), 1)
        self.assertIn('href="mailto:m@sveder.com?subject=Trip%20Companion%3A%20new%20place"', html)
        for name in ("Uzbekistan", "New York City", "Botswana", "Georgia", "Mongolia"):
            self.assertIn(f"<h3>{name}</h3>", html)
        for flag in ("botswana.svg", "georgia.svg", "mongolia.svg"):
            self.assertIn(f"img/flags/{flag}", html)
        self.assertIn("🗽", html)  # New York has no flag file: the emoji shows

    def test_hebrew_names_and_lines(self):
        from django.conf import settings
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "he"
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn('<html lang="he" dir="rtl">', html)
        for text in ("ניו יורק", "בוטסואנה", "גאורגיה", "מונגוליה", "בקשו מקום חדש"):
            self.assertIn(text, html)

    def test_trip_form_skips_the_request_card(self):
        user = get_user_model().objects.create_user("soon@example.com", "soon@example.com", "x")
        self.client.force_login(user)
        html = self.client.get(reverse("trip_setup")).content.decode()
        self.assertNotIn("mailto:", html)
        self.assertEqual(html.count('class="card country soon"'), 4)
        self.assertEqual(html.count("checked"), 1)  # Japan only, not every ready place
        html = self.client.get(reverse("trip_setup") + "?destination=uzbekistan").content.decode()
        self.assertIn('value="uzbekistan" checked', html)


class InJapanNowTests(TestCase):
    """T93: a trip with only a length (no leave date) can still reach the 'in Japan' part, with one tap."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.user = get_user_model().objects.create_user("n@example.com", "n@example.com")
        self.trip = make_trip(self.user, [38, 4])
        self.trip.set_dates(None, 12)
        self.trip.save()
        self.course = build_course(self.trip, [m.id for m, on in suggestions(self.trip) if on])
        self.client.force_login(self.user)

    def finish_all(self):
        for item in self.course.items.all():
            item.mark_done()

    def test_button_shows_on_finished_course_and_there_pages(self):
        self.finish_all()
        for url in ("/", reverse("course"), reverse("there")):
            html = self.client.get(url).content.decode()
            self.assertIn("We are in Japan now!", html, url)
            self.assertIn(reverse("in_japan_now"), html, url)
        self.assertNotIn("While we are there</a>", self.client.get("/").content.decode())

    def test_hebrew_button(self):
        self.client.cookies["django_language"] = "he"
        html = self.client.get(reverse("there"), HTTP_ACCEPT_LANGUAGE="he").content.decode()
        self.assertIn("אנחנו ביפן עכשיו!", html)

    def test_no_button_when_the_trip_has_a_date(self):
        self.trip.set_dates(timezone.localdate() + timedelta(days=30), 12)
        self.trip.save()
        self.assertNotIn("We are in Japan now!", self.client.get(reverse("there")).content.decode())
        self.trip.set_dates(timezone.localdate() - timedelta(days=1), 12)
        self.trip.save()
        self.assertNotIn("We are in Japan now!", self.client.get(reverse("there")).content.decode())

    def test_tap_starts_the_trip_today(self):
        from reminders.logic import HuntNote, due
        later = timezone.now() + timedelta(days=3)
        self.assertIsNotNone(due(self.user, now=later))
        self.assertNotIsInstance(due(self.user, now=later), HuntNote)
        self.assertEqual(self.client.get(reverse("in_japan_now")).status_code, 405)
        r = self.client.post(reverse("in_japan_now"))
        self.assertRedirects(r, reverse("there"))
        self.trip.refresh_from_db()
        today = timezone.localdate()
        self.assertEqual(self.trip.start_date, today)
        self.assertEqual(self.trip.end_date, today + timedelta(days=11))
        self.assertEqual(trip_phase(self.trip), "during")
        self.assertIsInstance(due(self.user, now=later), HuntNote)  # T78: in Japan the reminder is the hunt
        self.assertNotIn("We are in Japan now!", self.client.get(reverse("there")).content.decode())
        self.finish_all()
        html = self.client.get("/").content.decode()
        self.assertIn("While we are there", html)

    def test_first_visit_of_the_day_opens_the_photo_hunt(self):
        self.client.post(reverse("in_japan_now"))
        s = self.client.session
        s.pop("there_seen", None)
        s.save()
        self.assertRedirects(self.client.get("/"), reverse("there"))

    def test_second_tap_keeps_the_first_date(self):
        start = timezone.localdate() - timedelta(days=2)
        self.trip.set_dates(start, 12)
        self.trip.save()
        self.client.post(reverse("in_japan_now"))
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.start_date, start)


class TripEndTests(TestCase):
    """T110: a trip with no length and no date still ends: after DEFAULT_TRIP_DAYS, or when the family taps 'We are home!'."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.user = get_user_model().objects.create_user("h@example.com", "h@example.com")
        self.trip = make_trip(self.user, [38, 4])
        self.course = build_course(self.trip, [m.id for m, on in suggestions(self.trip) if on])
        self.client.force_login(self.user)

    def test_no_length_trip_ends_after_the_default_days(self):
        self.assertIsNone(self.trip.start_date)
        self.assertIsNone(self.trip.length_days)
        self.client.post(reverse("in_japan_now"))
        self.trip.refresh_from_db()
        today = timezone.localdate()
        self.assertEqual(trip_phase(self.trip, today + timedelta(days=13)), "during")
        self.assertEqual(trip_phase(self.trip, today + timedelta(days=15)), "after")
        self.assertEqual(trip_phase(self.trip, today + timedelta(days=14)), "after")

    def test_we_are_home_ends_the_trip_today(self):
        self.client.post(reverse("in_japan_now"))
        html = self.client.get(reverse("there")).content.decode()
        self.assertIn("We are home!", html)
        self.assertIn(reverse("back_home"), html)
        self.assertEqual(self.client.get(reverse("back_home")).status_code, 405)
        r = self.client.post(reverse("back_home"))
        self.assertRedirects(r, reverse("home"), fetch_redirect_response=False)
        self.trip.refresh_from_db()
        today = timezone.localdate()
        self.assertEqual(self.trip.end_date, today)
        self.assertEqual(self.trip.home_on, today)
        self.assertEqual(trip_phase(self.trip), "after")
        home = self.client.get("/").content.decode()
        self.assertIn("Words we met", home)
        self.assertNotIn("We are home!", self.client.get(reverse("there")).content.decode())

    def test_home_button_only_during_the_trip(self):
        self.assertNotIn("We are home!", self.client.get(reverse("there")).content.decode())

    def test_hebrew_home_button(self):
        self.client.post(reverse("in_japan_now"))
        self.client.cookies["django_language"] = "he"
        self.assertIn("חזרנו הביתה!", self.client.get(reverse("there")).content.decode())

    def test_new_dates_reopen_an_ended_trip(self):
        self.client.post(reverse("in_japan_now"))
        self.client.post(reverse("back_home"))
        self.trip.refresh_from_db()
        self.trip.set_dates(timezone.localdate() + timedelta(days=30), 10)
        self.trip.save()
        self.assertEqual(trip_phase(self.trip), "before")

    def test_reminders_stop_after_we_are_home(self):
        from reminders.logic import HuntNote, due
        self.client.post(reverse("in_japan_now"))
        self.client.post(reverse("back_home"))
        later = timezone.now() + timedelta(days=3)
        self.assertNotIsInstance(due(self.user, now=later), HuntNote)


class WhyDialogTests(TestCase):
    """T154: the word 'excited' on the welcome page buzzes and opens the 'why' dialog."""

    def test_english_word_and_dialog(self):
        html = self.client.get("/").content.decode()
        self.assertIn('<button type="button" class="buzz" data-why aria-haspopup="dialog">excited</button> for your trip!', html)
        self.assertIn('<dialog id="why"', html)
        self.assertIn("Half the fun is before you go", html)
        self.assertIn("Waiting for a trip is half the fun.", html)
        self.assertIn("Here your family learns what people eat, say and do where you are going.", html)
        self.assertIn("By the time you fly, everyone is excited.", html)
        self.assertIn("js/why.js", html)

    def test_hebrew_word_and_dialog(self):
        self.client.cookies["django_language"] = "he"
        html = self.client.get("/", HTTP_ACCEPT_LANGUAGE="he").content.decode()
        self.assertIn('data-why aria-haspopup="dialog">מתרגשים</button> לקראת הטיול!', html)
        self.assertIn("חצי מהכיף הוא לפני הטיול", html)
        self.assertIn("לחכות לטיול זה חצי מהכיף.", html)
        self.assertIn("כאן המשפחה שלכם לומדת", html)
        self.assertIn("כשתעלו על המטוס, כולם כבר יתרגשו.", html)

    def test_buzz_stops_for_reduced_motion(self):
        from django.conf import settings
        css = (settings.BASE_DIR / "static" / "css" / "app.css").read_text()
        self.assertIn("animation: buzz 5s ease-in-out infinite", css)
        self.assertRegex(css, r"prefers-reduced-motion: reduce\) \{ \.buzz \{ animation: none; \} \}")
        js = (settings.BASE_DIR / "static" / "js" / "why.js").read_text()
        self.assertIn("tc_why_seen", js)


class NewCourseTests(TestCase):
    """T155: home offers 'Go to our course' and 'New course'; a new course keeps the old one in Highlights."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.user = get_user_model().objects.create_user("n@example.com", "n@example.com")
        self.trip = make_trip(self.user, [38, 6])
        self.course = build_course(self.trip, [m.id for m, on in suggestions(self.trip) if on])
        self.first = self.course.next_item()
        self.first.mark_done()
        self.client.force_login(self.user)

    def test_home_shows_both_buttons(self):
        r = self.client.get("/")
        self.assertTemplateUsed(r, "courses/welcome.html")
        self.assertContains(r, f'href="{reverse("course")}"')
        self.assertContains(r, f'href="{reverse("new_trip")}"')
        self.assertContains(r, "Go to our course")
        self.assertNotContains(r, "Let's start")

    def test_hebrew_buttons_and_confirm(self):
        self.client.cookies["django_language"] = "he"
        r = self.client.get("/", HTTP_ACCEPT_LANGUAGE="he")
        self.assertContains(r, "למסלול שלנו")
        self.assertContains(r, "מסלול חדש")
        r = self.client.get(reverse("new_trip"), HTTP_ACCEPT_LANGUAGE="he")
        self.assertContains(r, "להתחיל מסלול חדש?")

    def test_course_page_links_to_a_new_course(self):
        self.assertContains(self.client.get(reverse("course")), f'href="{reverse("new_trip")}"')

    def test_get_asks_and_changes_nothing(self):
        r = self.client.get(reverse("new_trip"))
        self.assertContains(r, "Start a new course?")
        self.assertContains(r, "data-clear-state")
        self.assertEqual(Trip.objects.filter(user=self.user).count(), 1)

    def test_post_starts_a_fresh_course_and_keeps_the_old_one(self):
        r = self.client.post(reverse("new_trip"))
        self.assertRedirects(r, reverse("trip_setup") + "?new=1", fetch_redirect_response=False)
        trips = Trip.objects.filter(user=self.user).order_by("created_at", "id")
        self.assertEqual(trips.count(), 2)
        old, new = trips
        self.assertEqual(old.id, self.trip.id)
        self.assertEqual(sorted(new.ages), sorted(old.ages))
        self.assertEqual(new.destination, old.destination)
        self.assertFalse(Course.objects.filter(trip=new).exists())
        # The new trip is the active one: the course page sends the family to the builder.
        self.assertRedirects(self.client.get(reverse("course")), reverse("builder"), fetch_redirect_response=False)
        # The setup form for the new trip, then the builder.
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 1, "kid": 1, "big": 0, "little": 0})
        self.assertRedirects(r, reverse("builder"), fetch_redirect_response=False)
        self.assertEqual(Trip.objects.filter(user=self.user).count(), 2)
        # The old done mark is still there, and Highlights lists the old course.
        self.first.refresh_from_db()
        self.assertIsNotNone(self.first.done_at)
        page = self.client.get(reverse("highlights"))
        self.assertContains(page, "Our past courses")
        self.assertContains(page, f"?trip={old.id}")
        old_page = self.client.get(reverse("highlights") + f"?trip={old.id}")
        self.assertContains(old_page, self.first.activity.local_title)
        self.assertNotContains(old_page, "Our past courses")

    def test_other_family_trip_is_not_shown(self):
        other = make_trip(get_user_model().objects.create_user("o@example.com", "o@example.com"), [40])
        oc = build_course(other, [m.id for m, on in suggestions(other) if on])
        item = oc.next_item()
        item.mark_done()
        page = self.client.get(reverse("highlights") + f"?trip={other.id}")
        self.assertEqual(page.context["trip"].id, self.trip.id)
