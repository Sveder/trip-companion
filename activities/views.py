from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import select_template
from django.urls import reverse
from django.views.decorators.http import require_POST

from courses.models import CourseItem
from practice.items import add_items

from .links import find_link, visible_links
from .models import Clip, ReferralClick
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
    total = course.items.count()
    done = course.items.filter(done_at__isnull=False).count()
    act = item.activity
    hunt = None
    if act.type == "streetview":
        hunt = {"embed": streetview.embed_url(act.data), "link": streetview.maps_link(act.data),
                "missing": request.GET.get("missing") == "1"}
    template = select_template([f"activities/{item.activity.type}.html", "activities/coming_soon.html"])
    return render(
        request,
        template.template.name,
        {
            "item": item,
            "activity": item.activity,
            "module": item.activity.module,
            "data": item.activity.data,
            "trip": course.trip,
            "progress": {"done": done, "total": total, "number": item.order + 1},
            "steps": visible_steps(item.activity.data, course.trip) if item.activity.type == "steps" else None,
            "hunt": hunt,
            "links": visible_links(item.activity.data, course.trip) if item.activity.type == "links" else None,
        },
    )


@login_required
@require_POST
def activity_done(request, item_id):
    item = _item_for(request, item_id)
    act = item.activity
    if act.type == "streetview" and not item.done_at and not streetview.all_found(act.data, request.POST.getlist("found")):
        # A hunt is done only when every thing is found.
        return redirect(reverse("activity", args=[item.id]) + "?missing=1")
    item.mark_done()
    add_items(item.course.trip, item.activity)
    return redirect("home")


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
    return redirect(url)
