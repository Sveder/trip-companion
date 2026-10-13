"""Trip setup (feedback T264): two age groups and the module switches on one page."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from content_admin.models import Module
from courses.models import Course

from .models import GROUPS, Trip, family_line, group_of_age


class SetupPageTests(TestCase):
    """Feedback T264: one page sets up the adventure: the country, kids and grown-ups, the trip length and the modules."""

    def setUp(self):
        call_command("load_content", "japan", "uzbekistan", verbosity=0)
        self.user = get_user_model().objects.create_user("p@example.com", "p@example.com")
        self.client.force_login(self.user)

    def test_two_groups_only(self):
        self.assertEqual([g[0] for g in GROUPS], ["kid", "grownup"])

    def test_page_shows_steppers_and_module_switches_no_plane(self):
        page = self.client.get(reverse("trip_setup"))
        self.assertContains(page, "Who is coming?")
        for label in ("Kids", "Grown-ups"):
            self.assertContains(page, label)
        for gone in ("Big kids", "Little ones", "data-plane", "family.js", "on the plane"):
            self.assertNotContains(page, gone)
        self.assertContains(page, 'data-stepper="kid"')
        self.assertContains(page, 'data-step="1"')
        self.assertContains(page, "js/setup.js")
        self.assertContains(page, "For example 10")
        self.assertContains(page, 'id="modules"')
        self.assertContains(page, "Add all the kids activities")
        # Every Japan and Uzbekistan module has a switch; a new family gets every module that fits 1 kid + 2 grown-ups.
        for m in Module.objects.all():
            self.assertContains(page, f'name="modules" value="{m.id}" checked')
        self.assertContains(page, 'data-modules-for="japan"')
        self.assertContains(page, 'data-modules-for="uzbekistan"')
        self.assertContains(page, "Start our adventure!")

    def test_one_post_saves_the_trip_and_builds_the_course(self):
        japan = list(Module.objects.filter(country="japan").values_list("id", flat=True))
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 2, "kid": 1,
                                                     "modules_shown": 1, "modules": japan[:3]})
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)
        trip = Trip.objects.get()
        self.assertEqual(trip.group_counts, {"kid": 1, "grownup": 2})
        self.assertTrue(trip.has_child and trip.has_adult)
        self.assertEqual(sorted(Course.objects.get(trip=trip).module_ids), sorted(japan[:3]))

    def test_modules_of_another_country_are_ignored(self):
        uz = Module.objects.filter(country="uzbekistan").first()
        japan = Module.objects.filter(country="japan").first()
        self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 1, "modules_shown": 1,
                                                 "modules": [uz.id, japan.id]})
        self.assertEqual(Course.objects.get().module_ids, [japan.id])

    def test_no_module_is_refused(self):
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 1, "modules_shown": 1})
        self.assertContains(r, "Pick at least one thing to learn.")
        self.assertFalse(Trip.objects.exists())

    def test_a_form_without_switches_gets_the_modules_that_fit(self):
        self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 2})
        trip = Trip.objects.get()
        self.assertFalse(trip.has_child)
        kids_only = set(Module.objects.filter(country="japan", audience="child").values_list("id", flat=True))
        self.assertTrue(kids_only)
        self.assertFalse(kids_only & set(Course.objects.get(trip=trip).module_ids))

    def test_edit_shows_the_saved_counts_and_modules(self):
        japan = list(Module.objects.filter(country="japan").values_list("id", flat=True))
        self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 2, "kid": 3,
                                                 "modules_shown": 1, "modules": japan[:2]})
        page = self.client.get(reverse("trip_setup"))
        self.assertContains(page, 'name="kid" id="id_kid" min="0" max="12" inputmode="numeric" value="3"')
        self.assertContains(page, 'name="grownup" id="id_grownup" min="0" max="12" inputmode="numeric" value="2"')
        self.assertContains(page, f'name="modules" value="{japan[0]}" checked')
        self.assertNotContains(page, f'name="modules" value="{japan[2]}" checked')
        self.assertContains(page, "Save our adventure")

    def test_nobody_and_too_many_are_refused(self):
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "kid": 0, "grownup": 0})
        self.assertContains(r, "Add at least one person.")
        self.assertContains(r, '<div class="setup-error" role="alert">')
        r = self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 8, "kid": 5})
        self.assertContains(r, "up to 12 people")
        self.assertFalse(Trip.objects.exists())

    def test_old_ages_map_to_two_groups(self):
        self.assertEqual([group_of_age(a) for a in (0, 3, 4, 8, 9, 12, 13, 40)],
                         ["kid", "kid", "kid", "kid", "kid", "kid", "grownup", "grownup"])
        self.assertEqual(family_line({"grownup": 1, "kid": 2}), "1 grown-up, 2 kids")

    def test_hebrew_page(self):
        page = self.client.get(reverse("trip_setup") + "?lang=he")
        self.assertContains(page, "מי נוסע?")
        self.assertContains(page, "נבחר")
        self.assertContains(page, "יוצאים להרפתקה!")
        self.assertContains(page, "להוסיף את כל הפעילויות לילדים")

    def test_builder_url_opens_the_setup_page(self):
        self.assertRedirects(self.client.get(reverse("builder")), reverse("trip_setup"), fetch_redirect_response=False)
        self.client.post(reverse("trip_setup"), {"destination": "japan", "grownup": 1})
        self.assertRedirects(self.client.get(reverse("builder")), reverse("trip_setup") + "#modules", fetch_redirect_response=False)

    def test_tv_can_reach_and_flip_a_switch(self):
        js = (settings.BASE_DIR / "static/js/tv.js").read_text()
        self.assertIn(".switch-row'", js)
        self.assertIn("contains('switch-row')", js)


class TripLengthTests(TestCase):
    """Feedback T54: the leave date is optional, the family gives the trip length, and there is no return date field."""

    def setUp(self):
        call_command("load_content", verbosity=0)
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
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)
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
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)
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
    """T132: an edit of the length or the people goes back to the course. T264: a new course opens its first step."""

    FAMILY = {"destination": "japan", "grownup": 2, "kid": 1, "length_days": 10}

    def setUp(self):
        call_command("load_content", verbosity=0)
        self.user = get_user_model().objects.create_user("e@example.com", "e@example.com")
        self.client.force_login(self.user)

    def _with_course(self):
        self.client.post(reverse("trip_setup"), self.FAMILY)
        return Trip.objects.get()

    def _messages(self, r):
        from django.contrib.messages import get_messages
        return [str(m) for m in get_messages(r.wsgi_request)]

    def test_new_trip_opens_the_first_step(self):
        r = self.client.post(reverse("trip_setup"), self.FAMILY)
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)

    def test_edit_without_course_opens_the_first_step(self):
        self.client.post(reverse("trip_setup"), self.FAMILY)
        Course.objects.all().delete()
        r = self.client.post(reverse("trip_setup"), {**self.FAMILY, "length_days": 14})
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)

    def test_changed_destination_starts_a_new_course(self):
        trip = self._with_course()
        Trip.objects.filter(pk=trip.pk).update(destination="elsewhere")
        r = self.client.post(reverse("trip_setup"), self.FAMILY)
        self.assertRedirects(r, reverse("next_step"), fetch_redirect_response=False)

    def test_length_edit_goes_to_course(self):
        self._with_course()
        r = self.client.post(reverse("trip_setup"), {**self.FAMILY, "length_days": 14})
        self.assertRedirects(r, reverse("course"), fetch_redirect_response=False)
        self.assertIn("Trip updated.", self._messages(r))
        self.assertEqual(Trip.objects.get().length_days, 14)

    def test_people_edit_goes_to_course(self):
        self._with_course()
        r = self.client.post(reverse("trip_setup"), {**self.FAMILY, "kid": 3})
        self.assertRedirects(r, reverse("course"), fetch_redirect_response=False)
        self.assertEqual(Trip.objects.get().group_counts["kid"], 3)

    def test_hebrew_success_line(self):
        self._with_course()
        r = self.client.post(reverse("trip_setup") + "?lang=he", {**self.FAMILY, "length_days": 7},
                             HTTP_ACCEPT_LANGUAGE="he")
        self.assertRedirects(r, reverse("course"), fetch_redirect_response=False)
        self.assertIn("הטיול עודכן.", self._messages(r))


class SetupCssTests(TestCase):
    def test_switch_track_is_a_block(self):
        # T264: a <span> track with no display rule is inline, so its width and height were ignored and only the knob showed.
        css = (settings.BASE_DIR / "static/css/app.css").read_text()
        rule = css.split("\n.switch-row .switch {", 1)[1].split("}", 1)[0]
        self.assertIn("display: inline-block", rule)
