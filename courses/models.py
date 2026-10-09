from django.db import models
from django.utils import timezone

from content_admin.models import Activity
from trips.models import Trip

# Activity types that have a real player. Any other type, or a module with ready=False, is a
# "coming soon" stub: it cannot be marked done and the course goes past it.
PLAYABLE_TYPES = ("cards", "lesson", "links", "steps", "streetview", "words")


class Course(models.Model):
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="course")
    built_at = models.DateTimeField(default=timezone.now)
    module_ids = models.JSONField(default=list)

    def __str__(self):
        return f"Course for {self.trip}"

    def ready_items(self):
        return self.items.filter(activity__module__ready=True, activity__type__in=PLAYABLE_TYPES)

    def has_stubs(self):
        return self.items.count() > self.ready_items().count()

    def skipped_items(self):
        return self.ready_items().filter(done_at__isnull=False, found=0)

    def next_item(self, after=None):
        """The first unfinished activity. With `after`, the first unfinished one after that item,
        so a family that picks activity 9 on the course page goes on to 10, not back to 6."""
        todo = self.ready_items().filter(done_at__isnull=True).select_related("activity__module")
        if after is not None:
            later = todo.filter(order__gt=after.order).first()
            if later is not None:
                return later
        return todo.first()


class CourseItem(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveIntegerField()
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    done_at = models.DateTimeField(null=True, blank=True)
    # Street View hunts only: the best number of things the family found (T42). None = not a hunt, or not played.
    found = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["order"]

    @property
    def is_stub(self):
        return not self.activity.module.ready or self.activity.type not in PLAYABLE_TYPES

    def mark_done(self):
        if self.done_at is None:
            self.done_at = timezone.now()
            self.save(update_fields=["done_at"])

    @property
    def skipped(self):
        """A hunt ended with the skip button and nothing found (T121). It is played, so the course goes
        past it, but it is not done: no Done badge, no count in 'We did N of M', no every-activity party."""
        return self.done_at is not None and self.found == 0

    @property
    def is_done(self):
        return self.done_at is not None and not self.skipped

    @property
    def hunt_total(self):
        return len((self.activity.data or {}).get("spots", [])) if self.activity.type == "streetview" else None
