"""Suggest modules for a family, and build the course from the chosen modules."""
from django.db import transaction
from django.utils import timezone

from content_admin.models import Activity, Module

from .models import Course, CourseItem


def fits(module, trip):
    """True when the module's audience is in the family."""
    if module.audience == "child":
        return trip.has_child
    if module.audience == "adult":
        return trip.has_adult
    return True


def suggestions(trip):
    """Every module for the trip's country, each with suggested=True/False.

    Modules that do not fit stay in the list, switched off, so the parent can add them.
    """
    modules = Module.objects.filter(country=trip.destination).order_by("order", "slug")
    return [(m, fits(m, trip)) for m in modules]


@transaction.atomic
def build_course(trip, module_ids):
    """Write the course: one CourseItem per activity, in module order.

    A rebuild keeps the 'done' mark of activities that stay in the course.
    """
    course, created = Course.objects.get_or_create(trip=trip)
    done = {} if created else {i.activity_id: (i.done_at, i.found) for i in course.items.all()}
    modules = Module.objects.filter(country=trip.destination, id__in=module_ids)
    course.items.all().delete()
    activities = course_order(trip, Activity.objects.filter(module__in=modules))
    CourseItem.objects.bulk_create(
        CourseItem(course=course, order=n, activity=a, done_at=done.get(a.id, (None, None))[0], found=done.get(a.id, (None, None))[1])
        for n, a in enumerate(activities)
    )
    course.module_ids = sorted(m.id for m in modules)
    course.built_at = timezone.now()
    course.save()
    return course


def course_order(trip, activities):
    """The activities in course order: module by module, the rich lesson first in its module.

    The short card item of a module with a lesson comes after the lesson, as its quick review.
    """
    activities = sorted(
        activities.select_related("module"),
        key=lambda a: (a.module.order, a.module.slug, a.type != "lesson", a.order, a.slug),
    )
    return kids_first(activities) if trip.has_child else activities


def reorder_course(course):
    """Put the items of a built course in today's course order, in place.

    The items keep their ids, so clips, reminder links and done marks stay attached.
    Returns True when the order changed.
    """
    items = {i.activity_id: i for i in course.items.select_related("activity__module")}
    wanted = course_order(course.trip, Activity.objects.filter(id__in=items))
    if all(items[a.id].order == n for n, a in enumerate(wanted)):
        return False
    for n, a in enumerate(wanted):
        items[a.id].order = n
    CourseItem.objects.bulk_update(items.values(), ["order"])
    return True


def kids_first(activities):
    """Spread the kids' activities through the course, the first one as activity 2.

    A family with a child gets a made-for-kids activity early, then one every few
    activities, never two in a row while other activities are left. The other
    activities keep their order.
    """
    kids = [a for a in activities if a.module.audience == "child"]
    rest = [a for a in activities if a.module.audience != "child"]
    if not kids or not rest:
        return activities
    step = max(2, (len(rest) - 1) // len(kids))
    out = []
    for n, a in enumerate(rest):
        out.append(a)
        if kids and n % step == 0:
            out.append(kids.pop(0))
    return out + kids
