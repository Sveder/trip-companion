"""Test helpers for the courses app."""
from content_admin.models import Activity

from .models import CourseItem


def item_for(course, slug):
    """The course item of an activity, made at the end of the course when the course does not have it.

    T279: the quick review activities (cards, words, steps, links) stay in the content, but a course no longer
    gets them. Their players and their quiz feed are still tested through an item made here.
    """
    item = course.items.filter(activity__slug=slug).first()
    if item is None:
        activity = Activity.objects.get(module__country=course.trip.destination, slug=slug)
        item = CourseItem.objects.create(course=course, order=course.items.count(), activity=activity)
    return item
