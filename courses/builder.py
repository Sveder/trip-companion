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
    done = {} if created else {i.activity_id: i.done_at for i in course.items.all()}
    modules = Module.objects.filter(country=trip.destination, id__in=module_ids)
    course.items.all().delete()
    activities = Activity.objects.filter(module__in=modules).order_by("module__order", "module__slug", "order", "slug")
    CourseItem.objects.bulk_create(
        CourseItem(course=course, order=n, activity=a, done_at=done.get(a.id)) for n, a in enumerate(activities)
    )
    course.module_ids = sorted(m.id for m in modules)
    course.built_at = timezone.now()
    course.save()
    return course
