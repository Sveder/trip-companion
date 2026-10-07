from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import select_template
from django.views.decorators.http import require_POST

from courses.models import CourseItem
from practice.items import add_items


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
        },
    )


@login_required
@require_POST
def activity_done(request, item_id):
    item = _item_for(request, item_id)
    item.mark_done()
    add_items(item.course.trip, item.activity)
    return redirect("home")
