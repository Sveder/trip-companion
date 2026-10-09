"""What a family did, shown after the trip: activities done, saved clips, photos from the trip, words learned."""
from django.utils import timezone

from activities.models import Clip
from content_admin.i18n import localize
from practice.items import lookup
from practice.models import PracticeItem
from there.models import Photo
from there.things import THINGS


def trip_phase(trip, today=None):
    """'before', 'during' or 'after' the trip. A trip with no dates stays 'before'.
    A trip with a start and no length ends after DEFAULT_TRIP_DAYS; "We are home!" ends it that day (T110)."""
    today = today or timezone.localdate()
    if trip.home_on and today >= trip.home_on:
        return "after"
    last = trip.last_day
    if last and today > last:
        return "after"
    if trip.start_date and today >= trip.start_date:
        return "during"
    return "before"


def highlights(trip, course):
    done = []
    if course is not None:
        done = list(
            course.items.filter(done_at__isnull=False, activity__module__ready=True)
            .select_related("activity__module")
            .order_by("done_at")
        )
        # A hunt skipped with nothing found is not something "we did" (T42); the course offers it again.
        done = [i for i in done if i.found != 0]
    clips = list(Clip.objects.filter(trip=trip).order_by("created_at"))
    words = []
    for p in PracticeItem.objects.filter(trip=trip).order_by("added_at", "id"):
        activity, entry = lookup(trip, p.key)
        if activity is None or entry is None or activity.type != "words":
            continue
        words.append({"entry": localize(entry), "known": p.box >= 2})
    titles = {t["key"]: localize(t)["title"] for t in THINGS}
    photos = [{"photo": p, "title": titles.get(p.thing, "")} for p in Photo.objects.filter(trip=trip)]
    return {"done": done, "clips": clips, "photos": photos, "words": words}
