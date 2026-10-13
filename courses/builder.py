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


def fits_counts(module, counts):
    """fits() for a family that is not saved yet: {"kid": 1, "grownup": 2} (feedback T264)."""
    if module.audience == "child":
        return bool(counts.get("kid"))
    if module.audience == "adult":
        return bool(counts.get("grownup"))
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
    activities = course_order(trip, course_activities(modules))
    CourseItem.objects.bulk_create(
        CourseItem(course=course, order=n, activity=a, done_at=done.get(a.id, (None, None))[0], found=done.get(a.id, (None, None))[1])
        for n, a in enumerate(activities)
    )
    course.module_ids = sorted(m.id for m in modules)
    course.built_at = timezone.now()
    course.save()
    return course


def course_activities(modules):
    """The activities a course gets from these modules.

    T279 (Michael): no quick review rounds. A module with a lesson gives its lessons and hunts only;
    its short card item (flip cards, word cards, steps, links) stays in the content but not in the course.
    """
    from .models import REVIEW_TYPES

    with_lesson = Activity.objects.filter(module__in=modules, type="lesson").values("module_id")
    return Activity.objects.filter(module__in=modules).exclude(type__in=REVIEW_TYPES, module_id__in=with_lesson)


def course_order(trip, activities):
    """The activities in course order: module by module, the rich lesson first in its module.

    A module with no lesson keeps its short card item (T279 removed it from modules with a lesson).
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
    """Spread the kids' activities through the course, the first one after the first module.

    A family with a child gets a made-for-kids activity early, then one every few
    modules. A kids' activity goes only at a module edge, so a lesson and its quick
    review stay side by side. The other activities keep their order.
    """
    kids = [a for a in activities if a.module.audience == "child"]
    rest = [a for a in activities if a.module.audience != "child"]
    if not kids or not rest:
        return activities
    edges = [n for n, a in enumerate(rest) if n + 1 == len(rest) or rest[n + 1].module_id != a.module_id]
    step = max(1, (len(edges) - 1) // max(1, len(kids) - 1))
    at = set(edges[::step])
    out = []
    for n, a in enumerate(rest):
        out.append(a)
        if kids and n in at:
            out.append(kids.pop(0))
    return out + kids
