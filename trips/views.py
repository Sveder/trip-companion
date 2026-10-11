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
from courses.models import Course

from .forms import TripForm, country_choices
from .models import GROUPS, Traveller, Trip, active_trip


@family_required
def trip_setup(request):
    trip = active_trip(request.user)
    if request.method == "POST":
        form = TripForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                new = trip is None
                moved = not new and trip.destination != data["destination"]
                # T175: a new place on a trip that has a course starts a new trip (as 'New course' does),
                # so the old course and its done marks stay under 'Our past courses'.
                if moved and Course.objects.filter(trip=trip).exists():
                    trip, new = None, True
                if trip is None:
                    trip = Trip(user=request.user)
                trip.destination = data["destination"]
                trip.set_dates(data["start_date"], data["length_days"])
                trip.save()
                trip.travellers.all().delete()
                Traveller.objects.bulk_create(Traveller(trip=trip, age=a) for a in data["ages"])
            track("trip_set_up", trip=trip, new=new, travellers=len(data["ages"]))
            # T132: a new trip, a new place or no course yet goes to the builder; an edit of the
            # length or the people goes back to the course.
            if new or moved or not Course.objects.filter(trip=trip).exists():
                return redirect("builder")
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
    return render(request, "trips/setup.html", {
        "form": form, "previews": localize(load_previews()), "trip": trip,
        "groups": [{"id": g[0], "label": g[3], "emoji": g[4], "field": form[g[0]],
                    "range": f"{0 if i == 0 else GROUPS[i - 1][2] + 1}-{g[2]}" if g[0] != "grownup" else "13+"}
                   for i, g in enumerate(GROUPS)],
    })


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
