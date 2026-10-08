from datetime import date, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from courses.builder import build_course, suggestions
from courses.models import Course, CourseItem
from there.models import Photo
from trips.models import Traveller, Trip

from .logic import HuntNote, due, unsubscribe_token
from .models import Contact, ReminderLog


def family(email, start=None, length=None):
    user = get_user_model().objects.create_user(email, email)
    trip = Trip.objects.create(user=user, destination="japan", start_date=start, length_days=length,
                               end_date=start + timedelta(days=length - 1) if start and length else None)
    for age in (38, 4):
        Traveller.objects.create(trip=trip, age=age)
    build_course(trip, [m.id for m, on in suggestions(trip) if on])
    return user


def age_course(user, days):
    """Pretend the course was built `days` days ago and the family has not come back since."""
    Course.objects.filter(trip__user=user).update(built_at=timezone.now() - timedelta(days=days))


def run(*args):
    out = StringIO()
    call_command("send_reminders", *args, stdout=out, stderr=out)
    return out.getvalue()


class ReminderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def test_no_email_before_two_days(self):
        user = family("a@example.com")
        age_course(user, 1)
        self.assertIn("sent 0", run())
        self.assertEqual(len(mail.outbox), 0)

    def test_one_email_after_two_days_then_wait_again(self):
        user = family("a@example.com")
        age_course(user, 3)
        run()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["a@example.com"])
        item = Course.objects.get(trip__user=user).next_item()
        self.assertIn(f"/a/{item.id}/", msg.body)
        self.assertIn("/reminders/stop/", msg.body)
        self.assertIn("List-Unsubscribe", msg.extra_headers)
        self.assertEqual(ReminderLog.objects.filter(user=user).count(), 1)
        run()  # same day: the reminder itself counts as the last touch
        self.assertEqual(len(mail.outbox), 1)
        ReminderLog.objects.update(sent_at=timezone.now() - timedelta(days=2, minutes=1))
        run()
        self.assertEqual(len(mail.outbox), 2)

    def test_recent_visit_postpones(self):
        user = family("a@example.com")
        age_course(user, 5)
        Contact.objects.create(user=user, last_seen=timezone.now() - timedelta(hours=10))
        self.assertIsNone(due(user))

    def test_visit_is_recorded(self):
        user = family("a@example.com")
        self.client.force_login(user)
        self.client.get("/")
        self.assertIsNotNone(Contact.objects.get(user=user).last_seen)

    def test_none_when_course_finished(self):
        user = family("a@example.com")
        age_course(user, 3)
        Course.objects.get(trip__user=user).items.update(done_at=timezone.now())
        run()
        self.assertEqual(len(mail.outbox), 0)

    def test_no_course_item_once_trip_started(self):
        """From the leave date on, the reminder is the hunt (T78), never a course item."""
        for start, course_mail in ((date.today(), False), (date.today() - timedelta(days=3), False),
                                   (date.today() + timedelta(days=9), True)):
            user = family(f"{start}@example.com", start=start, length=10)
            age_course(user, 3)
            Trip.objects.filter(user=user).update(created_at=timezone.now() - timedelta(days=3))
            self.assertEqual(isinstance(due(user), CourseItem), course_mail, start)
            get_user_model().objects.filter(pk=user.pk).delete()

    def test_dry_run_lists_and_sends_nothing(self):
        user = family("a@example.com")
        age_course(user, 3)
        out = run("--dry-run")
        self.assertIn("would send a@example.com", out)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ReminderLog.objects.exists())

    def test_unsubscribe(self):
        user = family("a@example.com")
        age_course(user, 3)
        url = f"/reminders/stop/{unsubscribe_token(user)}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertIsNotNone(due(user), "opening the link alone must not unsubscribe")
        self.client.post(url)
        self.assertIsNone(due(user))
        run()
        self.assertEqual(len(mail.outbox), 0)
        self.client.post(url, {"again": "1"})
        self.assertIsNotNone(due(user))

    def test_bad_token_404(self):
        self.assertEqual(self.client.get("/reminders/stop/nonsense/").status_code, 404)


class ReminderLanguageTests(TestCase):
    """T55: a reminder goes out by cron, with no request, so it uses the language the family last used on the site."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def test_the_site_language_is_stored(self):
        user = family("a@example.com")
        self.client.force_login(user)
        self.client.get("/")
        self.assertEqual(Contact.objects.get(user=user).language, "en")
        self.client.get("/?lang=he")
        self.assertEqual(Contact.objects.get(user=user).language, "he")
        self.client.get("/")  # the cookie keeps Hebrew
        self.assertEqual(Contact.objects.get(user=user).language, "he")

    def test_hebrew_family_gets_hebrew_mail(self):
        user = family("he@example.com")
        self.client.force_login(user)
        self.client.get("/?lang=he")
        Contact.objects.filter(user=user).update(last_seen=timezone.now() - timedelta(days=3))
        age_course(user, 3)
        run()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        item = Course.objects.get(trip__user=user).next_item()
        title_he = item.activity.data.get("title_he")
        self.assertTrue(title_he)
        self.assertIn("הפעילות הבאה שלכם על יפן מחכה", msg.subject)
        self.assertIn("הפעילות הבאה שלכם על יפן מוכנה", msg.body)
        self.assertIn(title_he, msg.body)
        html = msg.alternatives[0][0]
        self.assertIn('dir="rtl"', html)
        self.assertIn(title_he, html)
        self.assertNotIn("Your next Japan activity", msg.body + html)
        self.assertIn("/reminders/stop/", msg.body)

    def test_english_family_gets_english_mail(self):
        user = family("en@example.com")
        age_course(user, 3)
        run()
        msg = mail.outbox[0]
        item = Course.objects.get(trip__user=user).next_item()
        self.assertIn("Your next Japan activity is waiting", msg.subject)
        self.assertIn(item.activity.title, msg.body)
        self.assertNotIn('dir="rtl"', msg.alternatives[0][0])
        self.assertNotIn("הפעילות", msg.body)


def in_japan(email, day=2, length=10, lang=None):
    """A family on day `day` of a `length`-day trip, quiet for three days."""
    user = family(email, start=date.today() - timedelta(days=day - 1), length=length)
    age_course(user, 3)
    Trip.objects.filter(user=user).update(created_at=timezone.now() - timedelta(days=3))
    if lang:
        Contact.objects.create(user=user, language=lang, last_seen=timezone.now() - timedelta(days=3))
    return user


class DuringTripReminderTests(TestCase):
    """T78: in Japan the reminder points to the 'While we are there' hunt, one thing per note."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def test_before_trip_mail_is_unchanged(self):
        user = family("a@example.com", start=date.today() + timedelta(days=9), length=7)
        age_course(user, 3)
        run()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Your next Japan activity is waiting", mail.outbox[0].subject)

    def test_during_trip_names_first_thing_and_links_to_hunt(self):
        user = in_japan("a@example.com")
        note = due(user)
        self.assertIsInstance(note, HuntNote)
        self.assertEqual(note.thing["key"], "manhole")
        run()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("Today in Japan, find: A pretty manhole cover", msg.subject)
        self.assertIn("/there/?from=reminder", msg.body)
        self.assertIn("You found 0 of 10 things.", msg.body)
        self.assertIn("/reminders/stop/", msg.body)
        self.assertIn("List-Unsubscribe", msg.extra_headers)
        log = ReminderLog.objects.get(user=user)
        self.assertIsNone(log.item)
        run()  # the gap holds: the hunt mail counts as the last touch
        self.assertEqual(len(mail.outbox), 1)

    def test_skips_things_with_a_photo(self):
        user = in_japan("a@example.com")
        trip = Trip.objects.get(user=user)
        for key in ("manhole", "pikachu"):
            Photo.objects.create(trip=trip, thing=key, file="photos/x.jpg")
        run()
        msg = mail.outbox[0]
        self.assertIn("A vending machine", msg.subject)
        self.assertIn("You found 2 of 10 things.", msg.body)

    def test_all_found_sends_nothing(self):
        from there.things import THINGS
        user = in_japan("a@example.com")
        trip = Trip.objects.get(user=user)
        for t in THINGS:
            Photo.objects.create(trip=trip, thing=t["key"], file="photos/x.jpg")
        self.assertIsNone(due(user))

    def test_recent_visit_postpones(self):
        user = in_japan("a@example.com")
        Contact.objects.create(user=user, last_seen=timezone.now() - timedelta(hours=10))
        self.assertIsNone(due(user))

    def test_after_trip_no_mail(self):
        user = in_japan("a@example.com", day=12, length=10)
        self.assertIsNone(due(user))
        run()
        self.assertEqual(len(mail.outbox), 0)

    def test_no_start_date_keeps_course_mail(self):
        user = family("a@example.com")
        age_course(user, 3)
        self.assertIsInstance(due(user), CourseItem)

    def test_hebrew_family_gets_hebrew_hunt_mail(self):
        in_japan("he@example.com", lang="he")
        run()
        msg = mail.outbox[0]
        self.assertIn("היום ביפן, מצאו: מכסה ביוב יפה", msg.subject)
        self.assertIn("מצאתם 0 מתוך 10 דברים.", msg.body)
        html = msg.alternatives[0][0]
        self.assertIn('dir="rtl"', html)
        self.assertIn("הסתכלו למטה!", html)
        self.assertNotIn("Today in Japan", msg.subject + msg.body + html)
