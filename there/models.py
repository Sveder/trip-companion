import uuid

from django.db import models
from django.utils import timezone

from activities.models import clip_storage


def photo_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"photos/{instance.trip_id}/{uuid.uuid4().hex}.{ext}"


class Photo(models.Model):
    """A photo a family took in Japan for the 'While we are there' hunt. Private, like the clips."""

    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE, related_name="photos")
    thing = models.CharField(max_length=30)
    file = models.FileField(storage=clip_storage, upload_to=photo_path)
    content_type = models.CharField(max_length=60, default="image/jpeg")
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Photo {self.id} ({self.thing}) for {self.trip}"
