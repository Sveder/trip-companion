from django.contrib import messages
from django.shortcuts import redirect, render
from accounts.guest import family_required
from django.utils import timezone
from django.utils.translation import gettext as _

from analytics.models import track
from content_admin.i18n import localize
from content_admin.loader import load_previews
from trips.models import Trip, active_trip

from .builder import build_course, suggestions
from .highlights import highlights as trip_highlights, trip_phase
from .models import Course


def home(request):
    """Signed out: the welcome page. Signed in: the next step for this family.
    T155: before the trip, a family part way through its course gets the welcome page with
    'Go to our course' and 'New course'."""
    if not request.user.is_authenticated:
        return render(request, "courses/welcome.html", {"previews": localize(load_previews())})
    return _next_step(request, welcome=True)


@family_required
def next_step(request):
    """The next activity, with no welcome page in between: after the builder and after a 'Next' button (T155)."""
    return _next_step(request, welcome=False)


def _next_step(request, welcome):
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    course = Course.objects.filter(trip=trip).first()
    phase = trip_phase(trip)
    if phase == "after":
        return _highlights_page(request, trip, course)
    if phase == "during" and request.session.get("there_seen") != str(timezone.localdate()):
        # In Japan, the first visit of the day opens the photo hunt. "Our course" is one tap away.
        request.session["there_seen"] = str(timezone.localdate())
        return redirect("there")
    if course is None:
        return redirect("builder")
    item = course.next_item()
    if item is None:
        return render(request, "courses/finished.html", {"trip": trip, "course": course, "phase": phase, "more_soon": course.has_stubs(),
                                                              "skipped": course.skipped_items().count()})
    if welcome and phase == "before":
        # T155: before the trip, home is the welcome page with "Go to our course" and "New course".
        return render(request, "courses/welcome.html", {"previews": localize(load_previews()), "course": course})
    return redirect("activity", item_id=item.id)


@family_required
def course(request):
    """The course as an ordered list. Every ready activity opens again, also after it is done."""
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    course = Course.objects.filter(trip=trip).first()
    if course is None:
        return redirect("builder")
    items = list(course.items.select_related("activity__module"))
    nxt = course.next_item()
    ready = [i for i in items if not i.is_stub]
    return render(request, "courses/course.html", {
        "trip": trip, "course": course, "items": items, "next_id": nxt.id if nxt else None, "phase": trip_phase(trip),
        "done": sum(1 for i in ready if i.is_done), "total": len(ready)})


@family_required
def builder(request):
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    course = Course.objects.filter(trip=trip).first()
    rows = suggestions(trip)
    if request.method == "POST":
        valid = {m.id for m, _ in rows}
        chosen = [int(x) for x in request.POST.getlist("modules") if x.isdigit() and int(x) in valid]
        if not chosen:
            messages.error(request, _("Pick at least one thing to learn."))
        else:
            before = set(course.module_ids) if course else set()
            course = build_course(trip, chosen)
            after = set(course.module_ids)
            track("course_built", trip=trip, modules=sorted(after), rebuild=bool(before))
            if before:
                for m in sorted(after - before):
                    track("module_added", trip=trip, module=m)
                for m in sorted(before - after):
                    track("module_removed", trip=trip, module=m)
            return redirect("next_step")
    on = set(course.module_ids) if course else {m.id for m, fit in rows if fit}
    modules = [{"module": m, "suggested": fit, "on": m.id in on} for m, fit in rows]
    return render(request, "courses/builder.html", {"trip": trip, "modules": modules, "course": course})


def _highlights_page(request, trip, course, past=False):
    # T155: the active trip's page lists the family's older courses, one line each.
    others = [] if past else list(Trip.objects.filter(user=request.user).exclude(id=trip.id))
    return render(request, "courses/highlights.html", {"trip": trip, "course": course, "phase": trip_phase(trip), "past": past,
                                                       "past_trips": others, **trip_highlights(trip, course)})


@family_required
def highlights(request):
    """The highlights page. Home shows it by itself after the trip; before that it is a preview.
    ?trip=<id> opens an older course of the same family (T155)."""
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    wanted = request.GET.get("trip", "")
    if wanted.isdigit() and int(wanted) != trip.id:
        old = Trip.objects.filter(user=request.user, id=int(wanted)).first()
        if old is not None:
            return _highlights_page(request, old, Course.objects.filter(trip=old).first(), past=True)
    return _highlights_page(request, trip, Course.objects.filter(trip=trip).first())
