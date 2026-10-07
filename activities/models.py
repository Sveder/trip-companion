import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone

# Family videos are private: they live outside MEDIA_ROOT (which nginx serves to anyone)
# and are only served by the clip view to the family that made them.
class ClipStorage(FileSystemStorage):
    """Reads CLIP_ROOT on every use, so tests (and a moved folder) need no restart."""

    @property
    def base_location(self):
        return str(settings.CLIP_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)


def clip_storage():
    return ClipStorage()


def clip_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    return f"{instance.trip_id}/{uuid.uuid4().hex}.{ext}"


class Clip(models.Model):
    """A short video a family recorded in a 'record' step and chose to save."""

    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE, related_name="clips")
    item = models.ForeignKey("courses.CourseItem", on_delete=models.SET_NULL, null=True, blank=True, related_name="clips")
    file = models.FileField(storage=clip_storage, upload_to=clip_path)
    content_type = models.CharField(max_length=60, default="video/webm")
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Clip {self.id} for {self.trip}"
