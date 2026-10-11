"""The family state as JSON, so the browser keeps a copy in localStorage (T144 part 2).

When the session cookie is gone (cleared cookies, a new browser profile on the same device), the
browser posts its copy back and gets the same trip, course, done marks and practice boxes again.
Hunt photos and recorded clips are files, so they stay with the old family.
"""
import datetime
import json

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_GET, require_POST

from tripapp.lang import CODES

from .guest import ensure_family, family_required, is_guest

VERSION = 1
MAX_BODY = 64 * 1024


def snapshot(user):
    """Everything a family chose and did, as plain JSON types."""
    from courses.models import Course
    from reminders.models import Contact
    from trips.models import active_trip

    contact = Contact.objects.filter(user=user).first()
    state = {"version": VERSION, "language": contact.language if contact else "en", "trip": None, "course": None, "practice": []}
    trip = active_trip(user)
    if trip is None:
        return state
    state["trip"] = {
        "destination": trip.destination,
        "start_date": _iso(trip.start_date),
        "length_days": trip.length_days,
        "home_on": _iso(trip.home_on),
        "travellers": [{"age": t.age} for t in trip.travellers.all()],
    }
    course = Course.objects.filter(trip=trip).first()
    if course is not None:
        items = course.items.select_related("activity__module")
        state["course"] = {
            "modules": sorted({i.activity.module.slug for i in items}),
            "items": [
                {"key": f"{i.activity.module.slug}/{i.activity.slug}", "done_at": _iso(i.done_at), "found": i.found}
                for i in items if i.done_at is not None
            ],
        }
    state["practice"] = [
        {"key": p.key, "box": p.box, "due_on": _iso(p.due_on), "last_result": p.last_result}
        for p in trip.practice_items.all()
    ]
    return state


@transaction.atomic
def restore(user, state):
    """Rebuild a family from a snapshot. Unknown modules, activities and bad values are skipped."""
    from content_admin.models import Module
    from courses.builder import build_course
    from practice.models import PracticeItem
    from reminders.models import Contact
    from trips.models import Traveller, Trip

    language = state.get("language")
    if language in CODES:
        Contact.objects.update_or_create(user=user, defaults={"language": language})
    data = state.get("trip")
    if not isinstance(data, dict):
        return
    trip = Trip(user=user, destination=str(data.get("destination") or "japan")[:40])
    trip.set_dates(_date(data.get("start_date")), _small_int(data.get("length_days")))
    trip.home_on = _date(data.get("home_on"))
    trip.save()
    ages = [_small_int(t.get("age")) for t in data.get("travellers") or [] if isinstance(t, dict)]
    Traveller.objects.bulk_create(Traveller(trip=trip, age=a) for a in ages[:20] if a is not None)

    course = state.get("course")
    if isinstance(course, dict):
        slugs = [s for s in course.get("modules") or [] if isinstance(s, str)]
        ids = list(Module.objects.filter(country=trip.destination, slug__in=slugs).values_list("id", flat=True))
        if ids:
            built = build_course(trip, ids)
            marks = {i["key"]: i for i in course.get("items") or [] if isinstance(i, dict) and isinstance(i.get("key"), str)}
            for item in built.items.select_related("activity__module"):
                mark = marks.get(f"{item.activity.module.slug}/{item.activity.slug}")
                done_at = _datetime(mark.get("done_at")) if mark else None
                if done_at:
                    item.done_at, item.found = done_at, _small_int(mark.get("found"))
                    item.save(update_fields=["done_at", "found"])

    rows = {}
    for p in state.get("practice") or []:
        if isinstance(p, dict) and isinstance(p.get("key"), str) and len(p["key"]) <= 200:
            rows[p["key"]] = PracticeItem(
                trip=trip, key=p["key"], box=max(1, min(_small_int(p.get("box")) or 1, 10)),
                due_on=_date(p.get("due_on")) or datetime.date.today(),
                last_result=p.get("last_result") if isinstance(p.get("last_result"), bool) else None)
    PracticeItem.objects.bulk_create(rows.values())


@family_required
@require_GET
def state_json(request):
    return JsonResponse(snapshot(request.user))


@require_POST
def state_restore(request):
    """POST a snapshot from localStorage. A browser whose family already has a trip keeps it and restores nothing.

    A browser that lost its cookies usually opens a family page first, which makes a new empty guest; the copy
    goes into that guest. Staff accounts are never overwritten.
    """
    user = request.user
    if user.is_authenticated and (not is_guest(user) or user.trips.exists()):
        return JsonResponse({"ok": False, "reason": "has a family"})
    if len(request.body) > MAX_BODY:
        return JsonResponse({"ok": False, "reason": "too big"}, status=400)
    try:
        state = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "reason": "bad json"}, status=400)
    if not isinstance(state, dict) or state.get("version") != VERSION:
        return JsonResponse({"ok": False, "reason": "bad state"}, status=400)
    with transaction.atomic():
        if not user.is_authenticated:
            user = ensure_family(request, method="restored")
        restore(user, state)
    response = JsonResponse({"ok": True})
    if state.get("language") in CODES:
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, state["language"], max_age=settings.SESSION_COOKIE_AGE,
                            samesite="Lax", secure=request.is_secure())
    return response


def _iso(value):
    return value.isoformat() if value else None


def _date(value):
    try:
        return parse_date(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _datetime(value):
    try:
        return parse_datetime(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _small_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 32767 else None
