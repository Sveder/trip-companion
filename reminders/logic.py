"""Who gets a reminder email, and the email itself."""
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db.models import Max
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation

from content_admin.i18n import localize
from content_admin.loader import load_previews
from courses.highlights import trip_phase
from courses.models import Course
from there.models import Photo
from there.things import THINGS
from trips.models import active_trip

from .models import Contact, ReminderLog

GAP = timedelta(days=2)
SALT = "reminders.unsubscribe"


def unsubscribe_token(user):
    return signing.dumps(user.pk, salt=SALT)


def user_from_token(token):
    try:
        return signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None


class HuntNote:
    """The during-trip reminder (T78): one thing from the 'While we are there' hunt, not a course item."""

    def __init__(self, trip, thing, found):
        self.trip, self.thing, self.found, self.total = trip, thing, found, len(THINGS)


def _last_touch(user, start):
    """The newest of: `start` (course built or trip made), last visit, last reminder."""
    times = [start]
    contact = Contact.objects.filter(user=user).first()
    if contact and contact.last_seen:
        times.append(contact.last_seen)
    sent = ReminderLog.objects.filter(user=user).aggregate(m=Max("sent_at"))["m"]
    if sent:
        times.append(sent)
    return max(times)


def due(user, now=None):
    """What this user should get a reminder about now, else None.

    Before the trip: the next CourseItem. During the trip: a HuntNote for the first thing on /there/
    with no photo yet. After the trip: nothing.
    """
    now = now or timezone.now()
    if not user.is_active or not user.email:
        return None
    if Contact.objects.filter(user=user, unsubscribed_at__isnull=False).exists():
        return None
    trip = active_trip(user)
    if trip is None:
        return None
    phase = trip_phase(trip, timezone.localdate(now))
    if phase == "after":
        return None
    if phase == "during":
        # T258: the photo hunt is a Japan list. Another country gets no mail during the trip.
        return _hunt_note(user, trip, now) if trip.destination == "japan" else None
    course = Course.objects.filter(trip=trip).first()
    if course is None:
        return None
    item = course.next_item()
    if item is None:
        return None
    if now - _last_touch(user, course.built_at) < GAP:
        return None
    return item


def _hunt_note(user, trip, now):
    have = set(Photo.objects.filter(trip=trip).values_list("thing", flat=True))
    left = [t for t in THINGS if t["key"] not in have]
    if not left:
        return None
    if now - _last_touch(user, trip.created_at) < GAP:
        return None
    return HuntNote(trip, left[0], len(THINGS) - len(left))


def build_email(user, item):
    """The reminder in the language the family last used on the site."""
    contact = Contact.objects.filter(user=user).first()
    with translation.override(contact.language if contact else settings.LANGUAGE_CODE):
        return _build_email(user, item)


def country_name(destination):
    """T258: the trip's place in the current language ('Japan', 'יפן', 'Uzbekistan')."""
    place = next((p for p in localize(load_previews()) if p["id"] == destination), None)
    return place["name"] if place else destination


def _build_email(user, item):
    base = settings.SITE_URL.rstrip("/")
    stop = base + reverse("reminders_stop", args=[unsubscribe_token(user)])
    if isinstance(item, HuntNote):
        name = "there_"
        ctx = {
            "thing": localize(item.thing),
            "found": item.found,
            "total": item.total,
            "go": base + reverse("there") + "?from=reminder",
        }
    else:
        name = ""
        ctx = {
            "item": item,
            "go": base + reverse("activity", args=[item.id]) + "?from=reminder",
            "left": item.course.ready_items().filter(done_at__isnull=True).count(),
            "place": country_name(item.course.trip.destination),
        }
    ctx["stop"] = stop
    subject = settings.ACCOUNT_EMAIL_SUBJECT_PREFIX + render_to_string(f"reminders/{name}subject.txt", ctx).strip()
    msg = EmailMultiAlternatives(
        subject,
        render_to_string(f"reminders/{name}email.txt", ctx),
        to=[user.email],
        headers={"List-Unsubscribe": f"<{stop}>"},
    )
    msg.attach_alternative(render_to_string(f"reminders/{name}email.html", ctx), "text/html")
    return msg


def describe(item):
    """One line for the command output."""
    if isinstance(item, HuntNote):
        return f"hunt: {item.thing['key']} ({item.found} of {item.total} found)"
    return f"{item.activity.module.title} / {item.activity.title} (item {item.id})"


def send(user, item, now=None):
    build_email(user, item).send()
    course_item = None if isinstance(item, HuntNote) else item
    ReminderLog.objects.create(user=user, item=course_item, sent_at=now or timezone.now())
