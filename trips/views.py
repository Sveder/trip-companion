from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from analytics.models import track
from content_admin.i18n import localize
from content_admin.loader import load_previews

from .forms import TripForm
from .models import GROUPS, Traveller, Trip, active_trip


@login_required
def trip_setup(request):
    trip = active_trip(request.user)
    if request.method == "POST":
        form = TripForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                new = trip is None
                if new:
                    trip = Trip(user=request.user)
                trip.destination = data["destination"]
                trip.set_dates(data["start_date"], data["length_days"])
                trip.save()
                trip.travellers.all().delete()
                Traveller.objects.bulk_create(Traveller(trip=trip, age=a) for a in data["ages"])
            track("trip_set_up", trip=trip, new=new, travellers=len(data["ages"]))
            return redirect("builder")
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
        form = TripForm(initial=initial)
    return render(request, "trips/setup.html", {
        "form": form, "previews": localize(load_previews()), "trip": trip,
        "groups": [{"id": g[0], "label": g[3], "emoji": g[4], "field": form[g[0]],
                    "range": f"{0 if i == 0 else GROUPS[i - 1][2] + 1}-{g[2]}" if g[0] != "grownup" else "13+"}
                   for i, g in enumerate(GROUPS)],
    })


@login_required
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
