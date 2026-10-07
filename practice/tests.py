from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

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

    def test_wrong_goes_back_to_box_one_due_next_visit(self):
        p = self.item(4)
        p.answer(False, today=TODAY)
        p.refresh_from_db()
        self.assertEqual((p.box, p.due_on, p.last_result), (1, TODAY, False))

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

    def test_words_activity_then_quiz_wrong_answer_comes_back(self):
        trip = make_trip(self.user)
        course = build_course(trip, list(Module.objects.filter(slug="words").values_list("id", flat=True)))
        item = course.items.get()
        self.client.force_login(self.user)
        page = self.client.get(reverse("activity", args=[item.id]))
        self.assertContains(page, "こんにちは")
        self.assertContains(page, 'data-say="こんにちは"')
        self.assertContains(self.client.get(reverse("quiz")), "No quiz yet")
        self.client.post(reverse("activity_done", args=[item.id]))
        n = PracticeItem.objects.filter(trip=trip).count()
        self.assertEqual(n, 7)

        page = self.client.get(reverse("quiz"))
        self.assertContains(page, f"Question 1 of {n}")
        q = page.context["q"]
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
        # The next quiz asks only the missed word.
        page = self.client.get(reverse("quiz") + "?new=1")
        self.assertContains(page, "Question 1 of 1")
        self.assertEqual(page.context["q"]["key"], missed.key)

    def test_quiz_ignores_a_stale_answer(self):
        trip = make_trip(self.user)
        PracticeItem.objects.create(trip=trip, key="words/words-intro/hai")
        self.client.force_login(self.user)
        self.client.get(reverse("quiz"))
        r = self.client.post(reverse("quiz"), {"key": "words/words-intro/oishii", "choice": "yummy"})
        self.assertRedirects(r, reverse("quiz"))
        self.assertIsNone(PracticeItem.objects.get(trip=trip).last_result)
