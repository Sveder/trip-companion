"""Trip setup (feedback T53): the family is four age groups on a plane, not a list of exact ages."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import GROUPS, Trip, family_line, group_of_age


class FamilyPlaneTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("p@example.com", "p@example.com")
        self.client.force_login(self.user)

    def test_at_most_four_groups(self):
        self.assertLessEqual(len(GROUPS), 4)

    def test_page_shows_the_plane_and_the_groups(self):
        page = self.client.get(reverse("trip_setup"))
        self.assertContains(page, "Put everyone on the plane")
        self.assertContains(page, "data-plane")
        for label in ("Little ones", "Kids", "Big kids", "Grown-ups"):
            self.assertContains(page, label)
        self.assertNotContains(page, "One number per person")
        self.assertContains(page, "js/family.js")
        # T109: the trip-length example is a hint under the box, not only a placeholder.
        self.assertContains(page, "For example 10")
        # T153: a side-view plane that keeps its shape (no stretching), with one wing and a fuselage to seat people in.
        self.assertContains(page, 'viewBox="0 0 400 190"')
        self.assertNotContains(page, 'preserveAspectRatio="none"')
        self.assertContains(page, 'class="fuselage"')
        # T153: family.js finds the plane box by its own attribute. The <body> also has data-family (T144),
        # and a shared name made the script take the body, so the plane and the people stayed hidden.
        self.assertContains(page, "data-family-pick")
        js = (settings.BASE_DIR / "static/js/family.js").read_text()
        self.assertIn('querySelector("[data-family-pick]")', js)

    def test_counts_become_travellers(self):
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 2, "kid": 1, "little": 1})
        self.assertRedirects(r, reverse("builder"))
        trip = Trip.objects.get()
        self.assertEqual(trip.group_counts, {"little": 1, "kid": 1, "big": 0, "grownup": 2})
        self.assertTrue(trip.has_child and trip.has_adult)
        self.assertContains(self.client.get(reverse("builder")), "2 grown-ups, 1 kid, 1 little one")

    def test_grown_ups_only_has_no_child(self):
        self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 2})
        trip = Trip.objects.get()
        self.assertFalse(trip.has_child)

    def test_edit_shows_the_saved_counts(self):
        self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 2, "big": 3})
        page = self.client.get(reverse("trip_setup"))
        self.assertContains(page, 'name="big" id="id_big" min="0" max="12" inputmode="numeric" value="3"')
        self.assertContains(page, 'name="grownup" id="id_grownup" min="0" max="12" inputmode="numeric" value="2"')

    def test_empty_plane_and_too_many_are_refused(self):
        r = self.client.post(reverse("trip_setup"), {"destination": "japan"})
        self.assertContains(r, "Put at least one person on the plane.")
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 8, "kid": 5})
        self.assertContains(r, "up to 12 people")
        self.assertFalse(Trip.objects.exists())

    def test_old_exact_ages_map_to_groups(self):
        self.assertEqual([group_of_age(a) for a in (0, 3, 4, 8, 9, 12, 13, 40)],
                         ["little", "little", "kid", "kid", "big", "big", "grownup", "grownup"])
        self.assertEqual(family_line({"grownup": 1, "big": 2}), "1 grown-up, 2 big kids")

    def test_hebrew_page(self):
        page = self.client.get(reverse("trip_setup") + "?lang=he")
        self.assertContains(page, "מטוס")

    def test_chosen_mark_and_next_step(self):
        # T166: the picked country says 'Chosen', and a link leads on to the family step.
        page = self.client.get(reverse("trip_setup"))
        self.assertContains(page, 'class="chosen-mark"')
        self.assertContains(page, 'href="#family" data-next-step')
        self.assertContains(page, 'id="family"')
        page = self.client.get(reverse("trip_setup") + "?lang=he")
        self.assertContains(page, "נבחר")
        self.assertContains(page, "הלאה: מי נוסע?")


class TripLengthTests(TestCase):
    """Feedback T54: the leave date is optional, the family gives the trip length, and there is no return date field."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("l@example.com", "l@example.com")
        self.client.force_login(self.user)

    def test_page_asks_for_length_not_return_date(self):
        page = self.client.get(reverse("trip_setup"))
        self.assertContains(page, "How many days is the trip?")
        self.assertContains(page, 'name="length_days"')
        self.assertContains(page, "We leave on (if you know)")
        self.assertNotContains(page, "We come home on")
        self.assertNotContains(page, 'name="end_date"')

    def test_length_without_a_date(self):
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 1, "length_days": 12})
        self.assertRedirects(r, reverse("builder"))
        trip = Trip.objects.get()
        self.assertEqual((trip.length_days, trip.start_date, trip.end_date), (12, None, None))

    def test_date_and_length_give_the_last_day(self):
        self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 1,
                                                 "start_date": "2026-11-10", "length_days": 10})
        trip = Trip.objects.get()
        self.assertEqual(str(trip.end_date), "2026-11-19")
        page = self.client.get(reverse("trip_setup"))
        self.assertContains(page, 'value="10"')

    def test_both_are_optional(self):
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 1})
        self.assertRedirects(r, reverse("builder"))
        self.assertIsNone(Trip.objects.get().length_days)

    def test_length_out_of_range_is_refused(self):
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 1, "length_days": 0})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Trip.objects.exists())

    def test_hebrew_labels(self):
        page = self.client.get(reverse("trip_setup") + "?lang=he")
        self.assertContains(page, "כמה ימים נמשך הטיול?")
        self.assertNotContains(page, "חוזרים הביתה בתאריך")


class TripEditTests(TestCase):
    """T132: an edit of the length or the people goes back to the course, not through the builder again."""

    FAMILY = {"destination": "japan", "grownup": 2, "kid": 1, "length_days": 10}

    def setUp(self):
        self.user = get_user_model().objects.create_user("e@example.com", "e@example.com")
        self.client.force_login(self.user)

    def _with_course(self):
        from courses.models import Course
        self.client.post(reverse("trip_setup"), self.FAMILY)
        trip = Trip.objects.get()
        Course.objects.create(trip=trip)
        return trip

    def _messages(self, r):
        from django.contrib.messages import get_messages
        return [str(m) for m in get_messages(r.wsgi_request)]

    def test_new_trip_goes_to_builder(self):
        r = self.client.post(reverse("trip_setup"), self.FAMILY)
        self.assertRedirects(r, reverse("builder"))

    def test_edit_without_course_goes_to_builder(self):
        self.client.post(reverse("trip_setup"), self.FAMILY)
        r = self.client.post(reverse("trip_setup"), {**self.FAMILY, "length_days": 14})
        self.assertRedirects(r, reverse("builder"))

    def test_changed_destination_goes_to_builder(self):
        trip = self._with_course()
        Trip.objects.filter(pk=trip.pk).update(destination="elsewhere")
        r = self.client.post(reverse("trip_setup"), self.FAMILY)
        self.assertRedirects(r, reverse("builder"))

    def test_length_edit_goes_to_course(self):
        self._with_course()
        r = self.client.post(reverse("trip_setup"), {**self.FAMILY, "length_days": 14})
        self.assertRedirects(r, reverse("course"), fetch_redirect_response=False)
        self.assertIn("Trip updated.", self._messages(r))
        self.assertEqual(Trip.objects.get().length_days, 14)

    def test_people_edit_goes_to_course(self):
        self._with_course()
        r = self.client.post(reverse("trip_setup"), {**self.FAMILY, "little": 1})
        self.assertRedirects(r, reverse("course"), fetch_redirect_response=False)
        self.assertEqual(Trip.objects.get().group_counts["little"], 1)

    def test_hebrew_success_line(self):
        self._with_course()
        r = self.client.post(reverse("trip_setup") + "?lang=he", {**self.FAMILY, "length_days": 7},
                             HTTP_ACCEPT_LANGUAGE="he")
        self.assertRedirects(r, reverse("course"), fetch_redirect_response=False)
        self.assertIn("הטיול עודכן.", self._messages(r))
