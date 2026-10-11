from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from courses.models import CourseItem

from .models import NAMES, Event, track

DAYS = 30


@require_POST
def video_play(request, item_id):
    """The step page posts here (sendBeacon) when a family starts a video."""
    if not request.user.is_authenticated:
        return HttpResponse(status=204)
    item = get_object_or_404(CourseItem.objects.select_related("course__trip"), id=item_id, course__trip__user=request.user)
    track("video_play", user=request.user, trip=item.course.trip, activity=item.activity_id,
          video=request.POST.get("video", "")[:40])
    return HttpResponse(status=204)


def funnel():
    """Families at each step, from the real tables, so families from before slice 11 count too."""
    users = get_user_model().objects.all()
    done = Count("trips__course__items", filter=Q(trips__course__items__done_at__isnull=False), distinct=True)
    users_done = users.annotate(done=done)
    steps = [
        ("Signed up", users.count()),
        ("Trip set up", users.filter(trips__isnull=False).distinct().count()),
        ("Course built", users.filter(trips__course__isnull=False).distinct().count()),
        ("First activity done", users_done.filter(done__gte=1).count()),
        ("3 activities done", users_done.filter(done__gte=3).count()),
    ]
    top = steps[0][1] or 1
    return [{"label": label, "count": n, "pct": round(100 * n / top)} for label, n in steps]


def stats(request):
    if not request.user.is_staff:
        raise PermissionDenied
    today = timezone.localdate()
    since = today - timedelta(days=DAYS - 1)
    rows = (
        Event.objects.filter(at__date__gte=since)
        .annotate(day=TruncDate("at"))
        .values("day", "name")
        .annotate(n=Count("id"))
    )
    table = {}
    for r in rows:
        table.setdefault(r["day"], {})[r["name"]] = r["n"]
    names = [n for n in NAMES if any(n in v for v in table.values())]
    days = [
        {"day": d, "cells": [table[d].get(n, 0) for n in names], "total": sum(table[d].values())}
        for d in sorted(table, reverse=True)
    ]
    totals = [sum(d["cells"][i] for d in days) for i in range(len(names))]
    links = (
        Event.objects.filter(name="referral_click").values("data__link").annotate(n=Count("id")).order_by("-n")
    )
    return render(request, "analytics/stats.html", {
        "funnel": funnel(),
        "names": [(n, NAMES[n]) for n in names],
        "days": days,
        "totals": totals,
        "grand_total": sum(totals),
        "links": [{"link": r["data__link"] or "?", "n": r["n"]} for r in links],
        "link_total": sum(r["n"] for r in links),
        "since": since,
        "all_time": Event.objects.count(),
    })
