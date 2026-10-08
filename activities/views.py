from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import select_template
from django.urls import reverse
from django.views.decorators.http import require_POST
from urllib.parse import urlencode

from analytics.models import track
from content_admin.i18n import localize
from courses.models import CourseItem
from practice.items import add_items

from .links import find_link, visible_links
from .models import Clip, ReferralClick
from .lesson import visible_pages
from .steps import visible_steps
from . import streetview

CLIP_TYPES = {"video/webm": "webm", "video/mp4": "mp4", "video/quicktime": "mov"}


def _item_for(request, item_id):
    return get_object_or_404(
        CourseItem.objects.select_related("activity__module", "course__trip"),
        id=item_id,
        course__trip__user=request.user,
    )


@login_required
def activity(request, item_id):
    item = _item_for(request, item_id)
    course = item.course
    ready = course.ready_items()
    total = ready.count()
    done = ready.filter(done_at__isnull=False).count()
    act = item.activity
    data = localize(act.data or {})
    if request.GET.get("from") == "reminder":
        track("reminder_click", trip=course.trip, activity=act.id)
    track("activity_opened", trip=course.trip, activity=act.id, module=act.module.slug)
    hunt = None
    if act.type == "streetview":
        hunt = {"embed": streetview.embed_url(act.data), "link": streetview.maps_link(act.data),
                "missing": request.GET.get("missing") == "1",
                "ticked": set(request.GET.get("found", "").split(","))}
    names = [f"activities/{act.type}.html"] if not item.is_stub else []
    template = select_template(names + ["activities/coming_soon.html"])
    return render(
        request,
        template.template.name,
        {
            "item": item,
            "activity": item.activity,
            "module": item.activity.module,
            "data": data,
            "trip": course.trip,
            "progress": None if item.is_stub else {
                "done": done, "total": total, "number": ready.filter(order__lt=item.order).count() + 1},
            "steps": visible_steps(data, course.trip) if item.activity.type == "steps" else None,
            "hunt": hunt,
            "links": visible_links(data, course.trip) if item.activity.type == "links" else None,
            "pages": visible_pages(data, course.trip) if item.activity.type == "lesson" else None,
        },
    )


@login_required
@require_POST
def activity_done(request, item_id):
    item = _item_for(request, item_id)
    act = item.activity
    if item.is_stub:
        # A "coming soon" stub never counts as done, so the family sees it when it turns real.
        return redirect("home")
    found_note = ""
    if act.type == "streetview":
        # A done hunt plays again from no ticks, so the same rules apply on a replay. The item stays done.
        found = request.POST.getlist("found")
        if not streetview.all_found(act.data, found):
            if request.POST.get("skip") != "1":
                # First press with things missing: "Keep looking!", the ticks stay, and a skip button appears.
                return redirect(reverse("activity", args=[item.id]) + "?" + urlencode(
                    {"missing": 1, "found": ",".join(found)}, safe=","))
            # A small child cannot always find them all. The skip button ends the hunt with the count found.
            found_note = "?" + urlencode({"found": streetview.count_found(act.data, found),
                                          "of": len(act.data.get("spots", []))})
    first_time = item.done_at is None
    if first_time:
        track("activity_done", trip=item.course.trip, activity=act.id, module=act.module.slug)
    item.mark_done()
    add_items(item.course.trip, item.activity)
    nxt = item.course.next_item(after=item)
    if nxt is None:
        return redirect("home")
    if first_time:
        # A short praise screen before the next activity. The last one goes to the finish page instead.
        return redirect(reverse("activity_praise", args=[item.id]) + found_note)
    return redirect("activity", item_id=nxt.id)


@login_required
def activity_praise(request, item_id):
    """'Great job!' between two activities: the guide cheers and the progress bar moves up one step."""
    item = _item_for(request, item_id)
    if item.done_at is None or item.is_stub:
        return redirect("activity", item_id=item.id)
    ready = item.course.ready_items()
    total = ready.count()
    done = ready.filter(done_at__isnull=False).count()
    found = of = None
    if item.activity.type == "streetview" and request.GET.get("found", "").isdigit() and request.GET.get("of", "").isdigit():
        found, of = int(request.GET["found"]), int(request.GET["of"])
    nxt = item.course.next_item(after=item)
    # The last activity of a module ends it: stars and a chime (feedback T83).
    module_done = not ready.filter(activity__module=item.activity.module, done_at__isnull=True).exists()
    return render(request, "activities/praise.html", {
        "module_done": module_done,
        "item": item, "next_url": reverse("activity", args=[nxt.id]) if nxt else reverse("home"), "activity": item.activity, "module": item.activity.module,
        "found": found if of and found < of else None, "of": of,
        "progress": {"done": done, "before": max(done - 1, 0), "total": total},
    })


@login_required
@require_POST
def clip_save(request, item_id):
    """Save the clip a family recorded in a 'record' step. The browser posts it as a file."""
    item = _item_for(request, item_id)
    upload = request.FILES.get("clip")
    if upload is None or upload.size == 0:
        return HttpResponseBadRequest("No clip.")
    if upload.size > settings.CLIP_MAX_BYTES:
        return HttpResponseBadRequest("The clip is too long.")
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type not in CLIP_TYPES:
        return HttpResponseBadRequest("Not a video.")
    upload.name = f"clip.{CLIP_TYPES[content_type]}"
    clip = Clip.objects.create(
        trip=item.course.trip, item=item, file=upload, content_type=content_type, size=upload.size
    )
    track("clip_saved", trip=item.course.trip, activity=item.activity_id, size=upload.size)
    return JsonResponse({"id": clip.id, "url": reverse("clip", args=[clip.id])})


@login_required
def clip_file(request, clip_id):
    clip = get_object_or_404(Clip, id=clip_id, trip__user=request.user)
    return FileResponse(clip.file.open("rb"), content_type=clip.content_type)


@login_required
def go(request, item_id, link_id):
    """Count a click on a shop link, then open the shop."""
    item = _item_for(request, item_id)
    url = find_link(item.activity, link_id)
    if url is None:
        raise Http404("No such link.")
    ReferralClick.objects.create(trip=item.course.trip, activity=item.activity, link_id=link_id, url=url)
    track("referral_click", trip=item.course.trip, activity=item.activity_id, link=link_id)
    return redirect(url)
