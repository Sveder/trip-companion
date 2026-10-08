from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from there.models import Photo
from there.shrink import shrink


class Command(BaseCommand):
    help = "Shrink the hunt photos already stored: upright, 1600 px, JPEG, no EXIF. Safe to run again."

    def handle(self, *args, **options):
        done = skipped = 0
        for photo in Photo.objects.all():
            with photo.file.open("rb") as f:
                data = f.read()
            small = shrink(data)
            if small is None or len(small[0]) >= len(data):
                skipped += 1
                continue
            old = photo.file.name
            photo.file.save("photo.jpg", ContentFile(small[0]), save=False)
            photo.content_type = "image/jpeg"
            photo.size = len(small[0])
            photo.save()
            photo.file.storage.delete(old)
            done += 1
            self.stdout.write(f"photo {photo.id}: {len(data)} -> {photo.size} bytes, {small[1]}x{small[2]}")
        self.stdout.write(f"shrunk {done}, kept {skipped}")
