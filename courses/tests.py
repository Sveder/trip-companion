import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from content_admin.models import Module
from courses.builder import build_course, suggestions
from courses.models import Course
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
        # Marking it done makes home open the next activity.
        c.post(reverse("activity_done", args=[first.id]))
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
