from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from content_admin.loader import load_previews
from trips.models import active_trip

from .builder import build_course, suggestions
from .models import Course


def home(request):
    """Signed out: the welcome page. Signed in: the next step for this family."""
    if not request.user.is_authenticated:
        return render(request, "courses/welcome.html", {"previews": load_previews()})
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    course = Course.objects.filter(trip=trip).first()
    if course is None:
        return redirect("builder")
    item = course.next_item()
    if item is None:
        return render(request, "courses/finished.html", {"trip": trip, "course": course})
    return redirect("activity", item_id=item.id)


@login_required
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
            messages.error(request, "Pick at least one thing to learn.")
        else:
            build_course(trip, chosen)
            return redirect("home")
    on = set(course.module_ids) if course else {m.id for m, fit in rows if fit}
    modules = [{"module": m, "suggested": fit, "on": m.id in on} for m, fit in rows]
    return render(request, "courses/builder.html", {"trip": trip, "modules": modules, "course": course})
