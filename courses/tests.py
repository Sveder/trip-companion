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
from courses.builder import build_course, suggestions
from courses.highlights import trip_phase
from courses.models import Course
from practice.models import PracticeItem
from trips.models import Traveller, Trip


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
        trip = make_trip(self.user, [38, 4])
        ids = [m.id for m, on in suggestions(trip) if on]
        course = build_course(trip, ids)
        items = list(course.items.select_related("activity__module"))
        self.assertEqual([i.order for i in items], list(range(len(items))))
        orders = [i.activity.module.order for i in items]
        self.assertEqual(orders, sorted(orders))
        self.assertEqual(items[0].activity.module.slug, "food")

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
        r = c.post(reverse("trip_setup"), {"destination": "japan", "ages": "38, 36, 4, 2"})
        self.assertRedirects(r, reverse("builder"))
        page = c.get(reverse("builder"))
        self.assertContains(page, "Street View hunt")
        # Parent adds "buy before you go" on top of the suggestion (it is suggested anyway here).
        ids = [str(m.id) for m in Module.objects.all()]
        r = c.post(reverse("builder"), {"modules": ids})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        course = Course.objects.get()
        first = course.items.first()
        r = c.get("/")
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
        self.assertRedirects(c.get("/"), reverse("activity", args=[second.id]))

    def test_other_users_activity_is_404(self):
        a = get_user_model().objects.create_user("a@example.com", "a@example.com")
        b = get_user_model().objects.create_user("b@example.com", "b@example.com")
        trip = make_trip(a, [30])
        course = build_course(trip, [m.id for m in Module.objects.all()])
        self.client.force_login(b)
        r = self.client.get(reverse("activity", args=[course.items.first().id]))
        self.assertEqual(r.status_code, 404)

    def test_bad_ages_rejected(self):
        u = get_user_model().objects.create_user("c@example.com", "c@example.com")
        self.client.force_login(u)
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "ages": "two"})
        self.assertContains(r, "is not an age")


class ThemeTests(TestCase):
    """Slice 3: every page wears the theme; the finish page celebrates."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("t@example.com", "t@example.com")

    def test_welcome_shows_the_guide_and_loads_theme(self):
        html = self.client.get("/").content.decode()
        self.assertIn('class="guide hero-guide"', html)
        self.assertIn("css/app.css", html)
        self.assertIn("js/celebrate.js", html)

    def test_welcome_ready_country_card_links_to_sign_in(self):
        html = self.client.get("/").content.decode()
        self.assertRegex(html, r'<a class="card country go" href="/signin/"')
        self.assertNotRegex(html, r'<a class="card country soon')

    def test_header_guide_is_decorative(self):
        html = self.client.get("/").content.decode()
        self.assertRegex(html, r'class="guide small"[^>]*aria-hidden="true"')

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

    def test_before_the_trip_home_opens_the_next_activity(self):
        self.set_dates(10, 20)
        r = self.client.get("/")
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
            self.assertRedirects(self.client.get("/"), reverse("activity", args=[item.id]))
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
        self.assertRedirects(self.client.get("/"), reverse("activity", args=[stub.id]))

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
        self.assertRedirects(self.client.get("/"), reverse("activity", args=[self.ready[1].id]))

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
        picked, after = self.ready[8], self.ready[9]
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
        self.assertRedirects(r, reverse("home"), fetch_redirect_response=False)

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

    def test_no_course_yet_goes_to_the_builder(self):
        self.course.delete()
        self.assertRedirects(self.client.get(reverse("course")), reverse("builder"))
