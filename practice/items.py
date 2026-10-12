"""Quiz items come from the content: every word of a `words` activity, every card marked `quiz: true`,
and the spots and flip cards of a `lesson` (at most LESSON_MAX of them)."""
import random

from django.templatetags.static import static
from django.utils.text import slugify
from django.utils.translation import gettext as _

from content_admin.i18n import is_hebrew, localize
from content_admin.models import Activity

from .models import PracticeItem

QUIZ_SIZE = 8
CHOICES = 4
# One lesson holds up to ~20 spots and cards. A cap keeps one lesson from filling every daily quiz.
LESSON_MAX = 12


def _card_id(card):
    return card.get("id") or slugify(card.get("title", ""))


def _text_entries(data, start):
    """One entry per text page that shows a word with a photo (a page with `img:` and `japanese:` or a picture).

    The label comes from the lesson's `pictures` list (the same word), so the answer is "Plov", not the page title.
    A picture marked `quiz: false` (itadakimasu among the foods) is not asked and is not a wrong choice.
    """
    pictures = data.get("pictures", [])
    out = []
    for n, page in enumerate(data.get("pages", [])):
        if page.get("kind") != "text" or not page.get("img"):
            continue
        pic = next((p for p in pictures if p.get("img") == page["img"] or (page.get("reading") and p.get("reading") == page["reading"])), {})
        # A page with no word of its own (tea, shoes off) counts when its photo is one of the lesson's pictures.
        if pic.get("quiz") is False or not (page.get("japanese") or pic):
            continue
        e = {
            "text_page": True,
            "page": start + n,
            "img": page["img"],
            "japanese": page.get("japanese", ""),
            "reading": page.get("reading", ""),
            "label": pic.get("label") or page.get("title", ""),
            "label_he": pic.get("label_he") or page.get("title_he", ""),
        }
        if pic.get("say_he"):
            e["reading_hebrew"] = pic["say_he"]
        out.append(e)
    return out


def _lesson_entries(data):
    """Every spot and flip card of a lesson, in page order, first copy of a repeated id only.

    Each entry is a copy that knows its page (`page`), so the wrong choices come from the same page:
    two cards on different pages can share one picture (nigiri and salmon both use sake.svg).
    A spot has no picture of its own, so it carries its page's picture (`page_img`).
    A lesson with fewer than CHOICES spots and flip cards (the Uzbek lessons, Food around Japan) also gives
    its word-and-photo text pages (T211); the other lessons do not read their text pages.
    """
    out, seen = [], set()
    pages = data.get("pages", [])
    for n, page in enumerate(pages):
        if page.get("kind") == "spots":
            items = [dict(s, page=n, page_img=page.get("img", "")) for s in page.get("spots", [])]
        elif page.get("kind") == "flip":
            items = [dict(c, page=n) for c in page.get("cards", [])]
        else:
            continue
        for e in items:
            i = slugify(e.get("reading", "")) or slugify(e.get("label", ""))
            if i and i not in seen:
                seen.add(i)
                out.append((i, e))
    if len(out) < CHOICES:
        for e in _text_entries(data, 0):
            i = slugify(e["reading"]) or slugify(e["label"])
            if i and i not in seen:
                seen.add(i)
                out.append((i, e))
        out.sort(key=lambda x: x[1]["page"])
    return out


def quiz_entries(activity, everything=False):
    """(item id, entry) pairs in one activity that the quiz can ask.

    A lesson gives its first LESSON_MAX entries; `everything=True` gives them all (to look up an old key).
    """
    data = activity.data or {}
    if activity.type == "lesson":
        entries = _lesson_entries(data)
        if everything:
            return entries
        # A spot with no Japanese reading cannot be asked ("Which one is ?"); it still serves as a wrong choice.
        askable = [(i, e) for i, e in entries if e.get("img") or e.get("reading")]
        # Take one from each page in turn, so the cap keeps a mix of pages and the quiz does not ask one page 8 times.
        pages = sorted({e["page"] for _, e in askable})
        queues = [[x for x in askable if x[1]["page"] == n] for n in pages]
        mixed = [q[k] for k in range(max(map(len, queues), default=0)) for q in queues if k < len(q)]
        return mixed[:LESSON_MAX]
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
    for i, entry in quiz_entries(activity, everything=True):
        if i == item_id:
            return activity, entry
    return activity, None


def question(trip, key):
    """A multiple-choice question for one practice item, or None when its content is gone.

    Words: the Japanese word, pick its meaning. Fact cards: the picture (or the card's own question), pick the name (or the card's own answer).
    Lesson flip cards: the picture, pick the name. Lesson spots: the page's picture and the Japanese reading, pick the name.
    Wrong choices come from the same activity (a lesson: the same page), so they are the same kind of thing.
    """
    activity, entry = lookup(trip, key)
    if entry is None:
        return None
    # Questions and choices in the active language. The answer check runs in the same language.
    entry = localize(entry)
    entries = [localize(e) for _, e in quiz_entries(activity)]
    if activity.type == "words":
        answer_of = lambda e: e["meaning"]
        q = {
            "kind": "word",
            "prompt": _("What does this word mean?"),
            "japanese": entry.get("japanese", ""),
            "reading": entry["reading"],
            "emoji": "",
        }
    elif activity.type == "lesson":
        answer_of = lambda e: e["label"]
        every = [localize(e) for _, e in quiz_entries(activity, everything=True)]
        entries = [e for e in every if e["page"] == entry["page"]]
        if len(entries) < CHOICES:
            # A small page (two spots in the shop) borrows from the other pages, but never a card with the same picture.
            entries = [e for e in every if e["page"] == entry["page"] or not (e.get("img") and e.get("img") == entry.get("img"))]
        img = entry.get("img") or entry.get("page_img", "")
        if entry.get("text_page"):
            # A word-and-photo text page: wrong choices are the other text pages of the lesson (other foods), never a flip card.
            entries = [e for e in every if e.get("text_page") and e["page"] != entry["page"]]
            if len(entries) < CHOICES - 1:
                # Three text pages only (Uzbek words): the flip cards fill the rest.
                entries = [e for e in every if e["page"] != entry["page"] and e.get("img") != entry["img"]]
            reading = entry.get("reading_hebrew") if is_hebrew() else entry.get("reading", "")
            # Hebrew has no Hebrew spelling of most readings yet (T197), and "איזה מהם נקרא osh?" mixes scripts.
            prompt = _("Which one is %(reading)s?") % {"reading": reading} if reading else _("What is this?")
        elif not entry.get("img"):
            # Hebrew asks with the reading in Hebrew letters ("נטה", not "neta"); `reading` stays Latin for the audio file (T123).
            reading = (is_hebrew() and entry.get("reading_hebrew")) or entry.get("reading", "")
            prompt = _("Which one is %(reading)s?") % {"reading": reading}
        elif activity.module.slug == "words":
            # A word card: the picture shows when you say the word.
            prompt = _("What do we say here?")
        else:
            prompt = _("What is this?")
        q = {
            "kind": "fact",
            "prompt": prompt,
            "japanese": entry.get("japanese", ""),
            "reading": entry.get("reading", ""),
            "emoji": "",
            "image": static(f"img/{img}") if img else "",
        }
        if not entry.get("img") and "x" in entry and "y" in entry:
            # A spot: a ring on the asked part of the page picture, so "Which one is neta?" points at the topping (T108).
            q["spot"] = {"x": entry["x"], "y": entry["y"]}
    else:
        # A card can name its own answer and wrong choices (e.g. "110" for the police card).
        # `choice: false` keeps a card that is not the same kind of thing (a phrase among foods) out of the wrong choices.
        answer_of = lambda e: str(e.get("answer") or e["title"])
        entries = [c for c in localize(activity.data.get("cards", [])) if not c.get("answer") and c.get("choice", True)]
        q = {
            "kind": "fact",
            "prompt": entry.get("question") or _("What is this?"),
            "japanese": entry.get("japanese", ""),
            "reading": entry.get("reading", ""),
            "emoji": entry.get("emoji", ""),
            "image": entry.get("image", ""),
        }
    right = answer_of(entry)
    rng = random.Random(f"{trip.id}:{key}")
    if entry.get("wrong"):
        others = sorted({str(w) for w in entry["wrong"]} - {right})
    else:
        others = sorted({answer_of(e) for e in entries} - {right})
    choices = rng.sample(others, min(CHOICES - 1, len(others))) + [right]
    rng.shuffle(choices)
    q.update({"key": key, "answer": right, "choices": choices, "module": activity.module})
    return q
