from datetime import timedelta

from django.db import models
from django.utils import timezone

from trips.models import Trip

BOXES = 5
# Days until the next ask after a right answer, by the box the item was in.
INTERVALS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}


class PracticeItem(models.Model):
    """One word or quiz fact that a family practises, in a Leitner box."""

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="practice_items")
    key = models.CharField(max_length=200, help_text="module/activity/item")
    box = models.PositiveSmallIntegerField(default=1)
    due_on = models.DateField(default=timezone.localdate)
    last_result = models.BooleanField(null=True, blank=True)
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["due_on", "box", "added_at", "id"]
        constraints = [models.UniqueConstraint(fields=["trip", "key"], name="unique_practice_key")]

    def __str__(self):
        return f"{self.key} (box {self.box})"

    def answer(self, right, today=None):
        """Right: one box up, asked again later. Wrong: back to box 1, asked again tomorrow.

        Not today: a child who just finished a quiz would get the same missed items at once, in a loop."""
        today = today or timezone.localdate()
        if right:
            self.due_on = today + timedelta(days=INTERVALS[self.box])
            self.box = min(self.box + 1, BOXES)
        else:
            self.box = 1
            self.due_on = today + timedelta(days=1)
        self.last_result = right
        self.save(update_fields=["box", "due_on", "last_result"])
