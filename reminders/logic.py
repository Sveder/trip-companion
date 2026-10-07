"""Who gets a reminder email, and the email itself."""
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db.models import Max
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from courses.models import Course
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


def _last_touch(user, course):
    """The newest of: course built, last visit, last reminder."""
    times = [course.built_at]
    contact = Contact.objects.filter(user=user).first()
    if contact and contact.last_seen:
        times.append(contact.last_seen)
    sent = ReminderLog.objects.filter(user=user).aggregate(m=Max("sent_at"))["m"]
    if sent:
        times.append(sent)
    return max(times)


def due(user, now=None):
    """The next CourseItem when this user should get a reminder now, else None."""
    now = now or timezone.now()
    if not user.is_active or not user.email:
        return None
    if Contact.objects.filter(user=user, unsubscribed_at__isnull=False).exists():
        return None
    trip = active_trip(user)
    if trip is None:
        return None
    if trip.start_date and trip.start_date <= timezone.localdate(now):
        return None
    course = Course.objects.filter(trip=trip).first()
    if course is None:
        return None
    item = course.next_item()
    if item is None:
        return None
    if now - _last_touch(user, course) < GAP:
        return None
    return item


def build_email(user, item):
    base = settings.SITE_URL.rstrip("/")
    stop = base + reverse("reminders_stop", args=[unsubscribe_token(user)])
    ctx = {
        "item": item,
        "go": base + reverse("activity", args=[item.id]),
        "stop": stop,
        "left": item.course.items.filter(done_at__isnull=True).count(),
    }
    subject = settings.ACCOUNT_EMAIL_SUBJECT_PREFIX + render_to_string("reminders/subject.txt", ctx).strip()
    msg = EmailMultiAlternatives(
        subject,
        render_to_string("reminders/email.txt", ctx),
        to=[user.email],
        headers={"List-Unsubscribe": f"<{stop}>"},
    )
    msg.attach_alternative(render_to_string("reminders/email.html", ctx), "text/html")
    return msg


def send(user, item, now=None):
    build_email(user, item).send()
    ReminderLog.objects.create(user=user, item=item, sent_at=now or timezone.now())
