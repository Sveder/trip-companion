from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from analytics.models import track
from trips.models import active_trip

from .items import due_items, question
from .models import PracticeItem

SESSION_KEY = "quiz"


def _start(request, trip):
    today = timezone.localdate()
    keys = [p.key for p in due_items(trip, today) if question(trip, p.key)]
    state = {"trip": trip.id, "keys": keys, "i": 0, "right": 0}
    request.session[SESSION_KEY] = state
    return state


@login_required
def quiz(request):
    """One question per page. A quiz holds at most 8 due items, earliest due first."""
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    state = request.session.get(SESSION_KEY)
    fresh = state is None or state.get("trip") != trip.id or request.GET.get("new") or (
        request.method == "GET" and state["i"] >= len(state["keys"]) and not request.GET.get("end")
    )
    if fresh and request.method == "GET":
        state = _start(request, trip)
    if not state["keys"]:
        nxt = PracticeItem.objects.filter(trip=trip).order_by("due_on").first()
        return render(request, "practice/empty.html", {"trip": trip, "next_item": nxt, "count": trip.practice_items.count()})

    if request.method == "POST" and state["i"] < len(state["keys"]):
        key = state["keys"][state["i"]]
        q = question(trip, key)
        if request.POST.get("key") != key or q is None:
            return redirect("quiz")
        chosen = request.POST.get("choice", "")
        right = chosen == q["answer"]
        item = PracticeItem.objects.filter(trip=trip, key=key).first()
        if item:
            item.answer(right)
        track("quiz_answer", trip=trip, key=key, right=right)
        state["i"] += 1
        state["right"] += int(right)
        request.session[SESSION_KEY] = state
        return render(request, "practice/quiz.html", _ctx(state, q, result={"right": right, "chosen": chosen}))

    if state["i"] >= len(state["keys"]):
        return render(request, "practice/done.html", {"right": state["right"], "total": len(state["keys"])})
    q = question(trip, state["keys"][state["i"]])
    if q is None:  # The content changed under a running quiz: start again.
        _start(request, trip)
        return redirect("quiz")
    return render(request, "practice/quiz.html", _ctx(state, q))


def _ctx(state, q, result=None):
    total = len(state["keys"])
    number = state["i"] if result else state["i"] + 1
    return {
        "q": q,
        "result": result,
        "progress": {"number": number, "total": total, "done": state["i"]},
        "last": state["i"] >= total,
    }
