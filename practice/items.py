"""Quiz items come from the content: every word of a `words` activity, and every card marked `quiz: true`."""
import random

from django.utils.text import slugify

from content_admin.models import Activity

from .models import PracticeItem

QUIZ_SIZE = 8
CHOICES = 4


def _card_id(card):
    return card.get("id") or slugify(card.get("title", ""))


def quiz_entries(activity):
    """(item id, entry) pairs in one activity that the quiz can ask."""
    data = activity.data or {}
    if activity.type == "words":
        return [(w.get("id") or slugify(w["reading"]), w) for w in data.get("words", [])]
    if activity.type == "cards":
        return [(_card_id(c), c) for c in data.get("cards", []) if c.get("quiz")]
    return []


def item_key(activity, item_id):
    return f"{activity.module.slug}/{activity.slug}/{item_id}"


def add_items(trip, activity):
    """Put the activity's words and quiz facts into practice. Items the family has already keep their box."""
    keys = [item_key(activity, i) for i, _ in quiz_entries(activity)]
    have = set(PracticeItem.objects.filter(trip=trip, key__in=keys).values_list("key", flat=True))
    PracticeItem.objects.bulk_create(PracticeItem(trip=trip, key=k) for k in keys if k not in have)
    return len(keys) - len(have)


def due_items(trip, today, limit=QUIZ_SIZE):
    """At most `limit` items due today or earlier, earliest due first."""
    return list(PracticeItem.objects.filter(trip=trip, due_on__lte=today).order_by("due_on", "box", "added_at", "id")[:limit])


def lookup(trip, key):
    """The activity and entry behind a key, or (None, None) when the content is gone."""
    try:
        module_slug, act_slug, item_id = key.split("/", 2)
    except ValueError:
        return None, None
    activity = (
        Activity.objects.select_related("module")
        .filter(module__country=trip.destination, module__slug=module_slug, slug=act_slug)
        .first()
    )
    if activity is None:
        return None, None
    for i, entry in quiz_entries(activity):
        if i == item_id:
            return activity, entry
    return activity, None


def question(trip, key):
    """A multiple-choice question for one practice item, or None when its content is gone.

    Words: the Japanese word, pick its meaning. Fact cards: the picture (or the card's own question), pick the name.
    Wrong choices come from the same activity, so they are the same kind of thing.
    """
    activity, entry = lookup(trip, key)
    if entry is None:
        return None
    entries = [e for _, e in quiz_entries(activity)]
    if activity.type == "words":
        answer_of = lambda e: e["meaning"]
        q = {
            "kind": "word",
            "prompt": "What does this word mean?",
            "japanese": entry.get("japanese", ""),
            "reading": entry["reading"],
            "emoji": "",
        }
    else:
        answer_of = lambda e: e["title"]
        entries = activity.data.get("cards", [])
        q = {
            "kind": "fact",
            "prompt": entry.get("question") or "What is this?",
            "japanese": "",
            "reading": "",
            "emoji": entry.get("emoji", ""),
            "image": entry.get("image", ""),
        }
    right = answer_of(entry)
    rng = random.Random(f"{trip.id}:{key}")
    others = sorted({answer_of(e) for e in entries} - {right})
    choices = rng.sample(others, min(CHOICES - 1, len(others))) + [right]
    rng.shuffle(choices)
    q.update({"key": key, "answer": right, "choices": choices, "module": activity.module})
    return q
