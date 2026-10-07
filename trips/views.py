from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from content_admin.loader import load_previews

from .forms import TripForm
from .models import Traveller, Trip, active_trip


@login_required
def trip_setup(request):
    trip = active_trip(request.user)
    if request.method == "POST":
        form = TripForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                if trip is None:
                    trip = Trip(user=request.user)
                trip.destination = data["destination"]
                trip.start_date = data["start_date"]
                trip.end_date = data["end_date"]
                trip.save()
                trip.travellers.all().delete()
                Traveller.objects.bulk_create(Traveller(trip=trip, age=a) for a in data["ages"])
            return redirect("builder")
    else:
        initial = {}
        if trip:
            initial = {
                "destination": trip.destination,
                "ages": ", ".join(str(a) for a in trip.ages),
                "start_date": trip.start_date,
                "end_date": trip.end_date,
            }
        form = TripForm(initial=initial)
    return render(request, "trips/setup.html", {"form": form, "previews": load_previews(), "trip": trip})
