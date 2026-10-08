from django.conf import settings
from django.db import models
from django.utils import timezone

# Every name the app writes. The stats page shows them in this order.
NAMES = {
    "signed_up": "Signed up",
    "signed_in": "Signed in",
    "trip_set_up": "Trip set up",
    "course_built": "Course built",
    "module_added": "Module added",
    "module_removed": "Module removed",
    "activity_opened": "Activity opened",
    "activity_done": "Activity done",
    "quiz_answer": "Quiz answer",
    "video_play": "Video played",
    "clip_saved": "Clip saved",
    "hunt_opened": "Photo hunt opened",
    "photo_saved": "Photo saved",
    "referral_click": "Shop link clicked",
    "reminder_click": "Reminder email opened",
}


class Event(models.Model):
    """One thing a family did. No third-party tracker: this table is all the analytics."""

    name = models.CharField(max_length=40, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    trip = models.ForeignKey("trips.Trip", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    data = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.name} {self.user_id} {self.at:%Y-%m-%d %H:%M}"


def track(name, user=None, trip=None, **data):
    """Write one event. Analytics never breaks a page, so errors are swallowed."""
    if name not in NAMES:
        raise ValueError(f"Unknown event {name!r}")
    if user is not None and not getattr(user, "is_authenticated", True):
        user = None
    if user is None and trip is not None:
        user = trip.user
    try:
        return Event.objects.create(name=name, user=user, trip=trip, data=data)
    except Exception:  # pragma: no cover - a full disk must not stop a child's activity
        return None
