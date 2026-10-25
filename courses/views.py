from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
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

# T310: the 2-minute demo video on the welcome page. Michael sets it Unlisted or Public on YouTube.
TOUR_VIDEO = "bsog6HsZj2I"


def home(request):
    """Signed out: the welcome page. Signed in: the next step for this family.
    T155: before the trip, a family part way through its course gets the welcome page with
    'Go to our course' and 'New course'."""
    if not request.user.is_authenticated:
        return render(request, "courses/welcome.html", {"previews": localize(load_previews()), "tour_video": TOUR_VIDEO})
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
        return redirect("trip_setup")
    item = course.next_item()
    if item is None:
        return render(request, "courses/finished.html", {"trip": trip, "course": course, "phase": phase, "more_soon": course.has_stubs(),
                                                              "skipped": course.skipped_items().count()})
    if welcome and phase == "before":
        # T155: before the trip, home is the welcome page with "Go to our course" and "New course".
        return render(request, "courses/welcome.html", {"previews": localize(load_previews()), "course": course,
                                                         "tour_video": TOUR_VIDEO})
    return redirect("activity", item_id=item.id)


@family_required
def course(request):
    """The course as an ordered list. Every ready activity opens again, also after it is done."""
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    course = Course.objects.filter(trip=trip).first()
    if course is None:
        return redirect("trip_setup")
    items = list(course.items.select_related("activity__module"))
    nxt = course.next_item()
    ready = [i for i in items if not i.is_stub]
    return render(request, "courses/course.html", {
        "trip": trip, "course": course, "items": items, "next_id": nxt.id if nxt else None, "phase": trip_phase(trip),
        "done": sum(1 for i in ready if i.is_done), "total": len(ready)})


@family_required
def builder(request):
    """Feedback T264: the module switches live on the trip page now. A GET opens that page;
    a POST (an old form or a bookmark) still rebuilds the course."""
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    if request.method == "POST":
        valid = {m.id for m, _ in suggestions(trip)}
        chosen = [int(x) for x in request.POST.getlist("modules") if x.isdigit() and int(x) in valid]
        if chosen:
            course = Course.objects.filter(trip=trip).first()
            before = set(course.module_ids) if course else set()
            course = build_course(trip, chosen)
            track("course_built", trip=trip, modules=sorted(course.module_ids), rebuild=bool(before))
            return redirect("next_step")
        messages.error(request, _("Pick at least one thing to learn."))
    return redirect(reverse("trip_setup") + "#modules")


def _highlights_page(request, trip, course, past=False):
    # T155: the active trip's page lists the family's older courses, one line each.
    others = [] if past else list(Trip.objects.filter(user=request.user).exclude(id=trip.id))
    return render(request, "courses/highlights.html", {"trip": trip, "course": course, "phase": trip_phase(trip), "past": past,
                                                       "past_trips": others, "has_quiz": trip.practice_items.exists(),
                                                       # T221: a screen reader reads an Uzbek word in an Uzbek voice, not a Japanese one.
                                                       "word_lang": "ja" if trip.destination == "japan" else "uz",
                                                       **trip_highlights(trip, course)})


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
