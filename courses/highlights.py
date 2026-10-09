"""What a family did, shown after the trip: activities done, saved clips, photos from the trip, words learned."""
from django.utils import timezone

from activities.models import Clip
from content_admin.i18n import localize
from content_admin.models import Activity
from practice.items import lookup, quiz_entries
from practice.models import PracticeItem
from there.models import Photo
from there.things import THINGS

# The "Words we met" list stops here: two full rows on the TV, a short scroll on a phone.
WORDS_MAX = 24


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
    titles = {t["key"]: localize(t)["title"] for t in THINGS}
    photos = [{"photo": p, "title": titles.get(p.thing, "")} for p in Photo.objects.filter(trip=trip)]
    return {"done": done, "clips": clips, "photos": photos, "words": met_words(trip)}


def met_words(trip):
    """Every practice item with a Japanese word: the words module first, then lesson spots and flip cards (T112).

    One card per Japanese word, at most WORDS_MAX. The meaning of a word comes from, in order (T134):
    a `words` activity entry with the same Japanese word ("thank you" for ありがとう, also when the family met it in a lesson),
    the entry's own `meaning`, then a lesson label for the same word on another page ("Tuna" names the まぐろ flip card),
    then its own label. A label that only repeats the reading ("Ebi" / ebi) gives no meaning.
    """
    meanings, names = {}, {}
    for a in Activity.objects.filter(type__in=["words", "lesson"], module__country=trip.destination):
        # A lesson's `pictures` (the game pictures) name words too: "Tuna" for まぐろ.
        for e in [e for _, e in quiz_entries(a, everything=True)] + (a.data or {}).get("pictures", []):
            if not e.get("japanese"):
                continue
            if e.get("meaning"):
                # A words-module meaning wins over a lesson's own meaning.
                if a.type == "words" or e["japanese"] not in meanings:
                    meanings[e["japanese"]] = localize(e)["meaning"]
            elif e.get("label") and e["label"].lower() != e.get("reading", "").lower():
                names.setdefault(e["japanese"], localize(e)["label"])
    first, rest, seen = [], [], set()
    for p in PracticeItem.objects.filter(trip=trip).order_by("added_at", "id"):
        activity, entry = lookup(trip, p.key)
        if activity is None or entry is None or not entry.get("japanese"):
            continue
        # The English label decides "only the reading": the Hebrew label is a transliteration (אריגטו) in that case too.
        reading_only = entry.get("label", "").lower() == entry.get("reading", "").lower()
        entry = localize(entry)
        if entry["japanese"] in seen:
            continue
        seen.add(entry["japanese"])
        meaning = meanings.get(entry["japanese"]) or names.get(entry["japanese"])
        if not meaning:
            meaning = "" if reading_only else entry.get("label", "")
        entry["meaning"] = meaning
        (first if activity.type == "words" or activity.module.slug == "words" else rest).append({"entry": entry, "known": p.box >= 2})
    return (first + rest)[:WORDS_MAX]
