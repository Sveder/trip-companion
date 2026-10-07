from django.db import models
from django.utils import timezone

from content_admin.models import Activity
from trips.models import Trip


class Course(models.Model):
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="course")
    built_at = models.DateTimeField(default=timezone.now)
    module_ids = models.JSONField(default=list)

    def __str__(self):
        return f"Course for {self.trip}"

    def next_item(self):
        return self.items.filter(done_at__isnull=True).select_related("activity__module").first()


class CourseItem(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveIntegerField()
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order"]

    def mark_done(self):
        if self.done_at is None:
            self.done_at = timezone.now()
            self.save(update_fields=["done_at"])
