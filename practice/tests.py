from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from content_admin.models import Activity, Module
from courses.builder import build_course
from courses.models import CourseItem
from trips.models import Traveller, Trip

from .items import add_items, due_items, question
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
        food = Activity.objects.get(slug="food-cards")
        add_items(self.trip, food)
        keys = set(PracticeItem.objects.filter(trip=self.trip).values_list("key", flat=True))
        marked = {c["title"] for c in food.data["cards"] if c.get("quiz")}
        self.assertEqual(len(keys), len(marked))
        self.assertIn("food/food-cards/sushi", keys)
        self.assertNotIn("food/food-cards/udon", keys)

    def test_question_has_the_answer_among_four_choices(self):
        q = question(self.trip, "words/words-intro/konnichiwa")
        self.assertEqual(q["answer"], "hello")
        self.assertEqual(len(q["choices"]), 4)
        self.assertIn("hello", q["choices"])
        q = question(self.trip, "food/food-cards/sushi")
        self.assertEqual(q["answer"], "Sushi")
        self.assertIn("Sushi", q["choices"])
        self.assertIsNone(question(self.trip, "food/food-cards/gone"))

    def test_food_quiz_asks_only_about_foods(self):
        food = Activity.objects.get(slug="food-cards")
        add_items(self.trip, food)
        keys = PracticeItem.objects.filter(trip=self.trip, key__startswith="food/").values_list("key", flat=True)
        self.assertNotIn("food/food-cards/itadakimasu", keys)
        for key in keys:
            q = question(self.trip, key)
            self.assertNotIn("Itadakimasu!", q["choices"])
            self.assertNotEqual(q["answer"], "Itadakimasu!")

    def test_itadakimasu_is_a_word(self):
        q = question(self.trip, "words/words-intro/itadakimasu")
        self.assertEqual(q["answer"], "thank you for the food")
        self.assertEqual(q["reading"], "itadakimasu")

    def test_stub_turned_ready_clears_old_done_marks(self):
        course = build_course(self.trip, list(Module.objects.values_list("id", flat=True)))
        item = course.items.get(activity__module__slug="words")
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

    def test_words_activity_then_quiz_wrong_answer_comes_back(self):
        trip = make_trip(self.user)
        course = build_course(trip, list(Module.objects.filter(slug="words").values_list("id", flat=True)))
        item = course.items.get()
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

    def test_quiz_ignores_a_stale_answer(self):
        trip = make_trip(self.user)
        PracticeItem.objects.create(trip=trip, key="words/words-intro/hai")
        self.client.force_login(self.user)
        self.client.get(reverse("quiz"))
        r = self.client.post(reverse("quiz"), {"key": "words/words-intro/oishii", "choice": "yummy"})
        self.assertRedirects(r, reverse("quiz"))
        self.assertIsNone(PracticeItem.objects.get(trip=trip).last_result)
