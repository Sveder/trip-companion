from django.contrib import messages
from accounts.guest import family_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from analytics.models import track
from content_admin.i18n import localize
from content_admin.loader import load_previews
from courses.builder import build_course
from courses.models import Course

from .forms import TripForm, country_choices
from .models import GROUPS, Traveller, Trip, active_trip


def _module_rows(trip, counts, course):
    """Feedback T264: the module switches for every ready country, so a country change needs no reload.
    A switch is on when the family's course has the module, or (no course yet) when the module fits the family."""
    from content_admin.models import Module
    from courses.builder import fits_counts
    rows = {}
    on = set(course.module_ids) if course else None
    for m in Module.objects.order_by("order", "slug"):
        if on is not None and trip and m.country == trip.destination:
            is_on = m.id in on
        else:
            is_on = fits_counts(m, counts)
        rows.setdefault(m.country, []).append({"module": m, "on": is_on})
    return rows


@family_required
def trip_setup(request):
    """Feedback T264: one page sets up the whole adventure: the country, who is coming, the trip length
    and the modules. The 'Start our adventure' button saves the trip and builds the course."""
    trip = active_trip(request.user)
    course = Course.objects.filter(trip=trip).first() if trip else None
    if request.method == "POST":
        form = TripForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                new = trip is None
                moved = not new and trip.destination != data["destination"]
                # T175: a new place on a trip that has a course starts a new trip (as 'New course' does),
                # so the old course and its done marks stay under 'Our past courses'.
                if moved and course is not None:
                    trip, new, course = None, True, None
                if trip is None:
                    trip = Trip(user=request.user)
                trip.destination = data["destination"]
                trip.set_dates(data["start_date"], data["length_days"])
                trip.save()
                trip.travellers.all().delete()
                Traveller.objects.bulk_create(Traveller(trip=trip, age=a) for a in data["ages"])
                before = set(course.module_ids) if course else set()
                built = build_course(trip, data["modules"])
            track("trip_set_up", trip=trip, new=new, travellers=len(data["ages"]))
            after = set(built.module_ids)
            track("course_built", trip=trip, modules=sorted(after), rebuild=bool(before))
            if before:
                for m in sorted(after - before):
                    track("module_added", trip=trip, module=m)
                for m in sorted(before - after):
                    track("module_removed", trip=trip, module=m)
            # T132: a new course opens its first step; an edit goes back to the course list.
            if course is None:
                return redirect("next_step")
            messages.success(request, _("Trip updated."))
            return redirect("course")
    else:
        initial = {}
        if trip:
            initial = {
                "destination": trip.destination,
                **trip.group_counts,
                "start_date": trip.start_date,
                "length_days": trip.length_days or (
                    (trip.end_date - trip.start_date).days + 1 if trip.start_date and trip.end_date else None),
            }
        # T171: a country card on the welcome page opens the form with that country chosen.
        if request.GET.get("destination") in dict(country_choices()):
            initial["destination"] = request.GET["destination"]
        form = TripForm(initial=initial)
    if form.is_bound:
        counts = {g[0]: _int(form.data.get(g[0])) for g in GROUPS}
        picked = {_int(x) for x in form.data.getlist("modules")}
        rows = _module_rows(None, counts, None)
        for country_rows in rows.values():
            for r in country_rows:
                r["on"] = r["module"].id in picked
    else:
        counts = {g[0]: form.initial.get(g[0], form.fields[g[0]].initial) for g in GROUPS}
        rows = _module_rows(trip, counts, course)
    previews = localize(load_previews())
    return render(request, "trips/setup.html", {
        "form": form, "previews": previews, "trip": trip, "course": course,
        "groups": [{"id": g[0], "label": g[3], "field": form[g[0]], "value": counts[g[0]],
                    "range": "0-12" if g[0] == "kid" else "13+"} for g in GROUPS],
        "module_sets": [{"country": c["id"], "rows": rows.get(c["id"], [])} for c in previews if c.get("ready") and not c.get("href")],
    })


def _int(v):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


@family_required
@require_POST
def in_japan_now(request):
    """T93: a trip with no leave date starts today, so the 'in Japan' part (photo hunt, highlights) switches on."""
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    if trip.start_date is None:
        trip.set_dates(timezone.localdate(), trip.length_days)
        trip.save(update_fields=["start_date", "end_date", "length_days"])
        track("trip_started_now", trip=trip)
        messages.success(request, _("Have a great trip! Here is your photo list."))
    request.session["there_seen"] = str(timezone.localdate())
    return redirect("there")


@family_required
@require_POST
def back_home(request):
    """T110: 'We are home!' ends the trip today, so home shows the highlights."""
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    today = timezone.localdate()
    if trip.start_date is None or trip.start_date > today:
        trip.start_date = today
    trip.end_date, trip.home_on = today, today
    trip.length_days = (today - trip.start_date).days + 1
    trip.save(update_fields=["start_date", "end_date", "length_days", "home_on"])
    track("trip_ended_now", trip=trip)
    messages.success(request, _("Welcome home! Here is what you did."))
    return redirect("home")


@family_required
def new_trip(request):
    """T155: 'New course'. GET asks once; POST starts a new trip with the same place and people.
    The old trip and its course stay, so Highlights still lists what the family did."""
    old = active_trip(request.user)
    if old is None:
        return redirect("trip_setup")
    if request.method != "POST":
        return render(request, "trips/new.html", {"trip": old})
    with transaction.atomic():
        trip = Trip.objects.create(user=request.user, destination=old.destination)
        Traveller.objects.bulk_create(Traveller(trip=trip, age=t.age) for t in old.travellers.all())
    track("trip_set_up", trip=trip, new=True, travellers=trip.travellers.count(), restart=True)
    return redirect(reverse("trip_setup") + "?new=1")
