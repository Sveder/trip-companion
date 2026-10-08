import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from courses.builder import build_course, suggestions
from trips.models import Traveller, Trip

from .models import Photo
from .things import THINGS

PHOTO_DIR = tempfile.mkdtemp(prefix="trip-photos-")
# The smallest valid GIF and a JPEG header are enough: the server checks the type, not the pixels.
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200


def jpeg(name="p.jpg"):
    return SimpleUploadedFile(name, JPEG, content_type="image/jpeg")


@override_settings(CLIP_ROOT=PHOTO_DIR)
class WhileWeAreThereTests(TestCase):
    """T52 (Michael's feedback): a photo hunt during the trip that feeds the after-trip highlights."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def setUp(self):
        self.user = get_user_model().objects.create_user("t@example.com", "t@example.com")
        self.trip = Trip.objects.create(user=self.user, destination="japan")
        for a in (40, 4):
            Traveller.objects.create(trip=self.trip, age=a)
        self.course = build_course(self.trip, [m.id for m, on in suggestions(self.trip) if on])
        self.client.force_login(self.user)

    def set_dates(self, start_in, end_in):
        today = timezone.localdate()
        self.trip.start_date = today + timedelta(days=start_in)
        self.trip.end_date = today + timedelta(days=end_in)
        self.trip.save()

    def test_list_shows_every_thing_with_a_photo_button(self):
        html = self.client.get(reverse("there")).content.decode()
        self.assertIn("While we are there", html)
        self.assertIn("A pretty manhole cover", html)
        self.assertIn("Pikachu", html)
        self.assertEqual(html.count('class="there-add"'), len(THINGS))
        self.assertIn('accept="image/*"', html)
        self.assertIn(f"0 of {len(THINGS)} found", html)

    def test_a_photo_ticks_the_thing_and_only_the_family_sees_it(self):
        r = self.client.post(reverse("there_add", args=["manhole"]), {"photo": jpeg()})
        self.assertRedirects(r, reverse("there") + "#manhole", fetch_redirect_response=False)
        photo = Photo.objects.get(trip=self.trip)
        self.assertEqual(photo.thing, "manhole")
        self.assertTrue(Path(photo.file.path).is_file())
        self.assertTrue(str(photo.file.path).startswith(PHOTO_DIR))
        html = self.client.get(reverse("there")).content.decode()
        self.assertIn("Great find!", html)
        self.assertIn(f"1 of {len(THINGS)} found", html)
        self.assertIn(reverse("photo", args=[photo.id]), html)
        r = self.client.get(reverse("photo", args=[photo.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), JPEG)
        other = get_user_model().objects.create_user("o@example.com", "o@example.com")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("photo", args=[photo.id])).status_code, 404)

    def test_bad_uploads_are_refused(self):
        bad = SimpleUploadedFile("x.txt", b"hello", content_type="text/plain")
        self.assertEqual(self.client.post(reverse("there_add", args=["manhole"]), {"photo": bad}).status_code, 400)
        self.assertEqual(self.client.post(reverse("there_add", args=["manhole"]), {}).status_code, 400)
        self.assertEqual(self.client.post(reverse("there_add", args=["dragon"]), {"photo": jpeg()}).status_code, 404)
        with self.settings(PHOTO_MAX_BYTES=10):
            self.assertEqual(self.client.post(reverse("there_add", args=["manhole"]), {"photo": jpeg()}).status_code, 400)
        self.assertFalse(Photo.objects.exists())

    def test_remove_a_photo(self):
        self.client.post(reverse("there_add", args=["pikachu"]), {"photo": jpeg()})
        photo = Photo.objects.get()
        path = Path(photo.file.path)
        self.client.post(reverse("photo_delete", args=[photo.id]))
        self.assertFalse(Photo.objects.exists())
        self.assertFalse(path.exists())

    def test_photos_feed_the_after_trip_highlights(self):
        self.client.post(reverse("there_add", args=["manhole"]), {"photo": jpeg()})
        self.client.post(reverse("there_add", args=["pikachu"]), {"photo": jpeg()})
        self.set_dates(-20, -1)
        html = self.client.get("/").content.decode()
        self.assertIn("Welcome back from Japan!", html)
        self.assertIn("What we found in Japan", html)
        for p in Photo.objects.all():
            self.assertIn(reverse("photo", args=[p.id]), html)
        self.assertIn("A pretty manhole cover", html)

    def test_in_japan_home_opens_the_hunt_once_a_day(self):
        self.set_dates(-2, 5)
        self.assertRedirects(self.client.get("/"), reverse("there"), fetch_redirect_response=False)
        r = self.client.get("/")
        self.assertRedirects(r, reverse("activity", args=[self.course.next_item().id]), fetch_redirect_response=False)

    def test_before_the_trip_home_keeps_the_course_and_the_list_says_it_is_for_later(self):
        self.set_dates(10, 20)
        r = self.client.get("/")
        self.assertRedirects(r, reverse("activity", args=[self.course.next_item().id]), fetch_redirect_response=False)
        self.assertIn("This list is for the trip.", self.client.get(reverse("there")).content.decode())

    def test_hebrew(self):
        self.client.post(reverse("set_language"), {"language": "he", "next": "/"})
        html = self.client.get(reverse("there")).content.decode()
        self.assertIn("מכסה ביוב יפה", html)
        self.assertIn("בזמן שאנחנו שם", html)
        self.assertIn('dir="rtl"', html)
        for t in THINGS:
            self.assertTrue(t["title_he"] and t["hint_he"], t["key"])


def phone_jpeg(width=4000, height=3000, orientation=6):
    """A real JPEG like a phone writes: big, stored sideways with an EXIF turn, and a GPS position."""
    import io

    from PIL import Image

    img = Image.new("RGB", (width, height), "red")
    img.paste((0, 0, 255), (0, 0, width // 2, height))  # left half blue, so the turn can be checked
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x8825] = {1: "N", 2: (35.0, 39.0, 0.0), 3: "E", 4: (139.0, 42.0, 0.0)}
    out = io.BytesIO()
    img.save(out, "JPEG", quality=95, exif=exif)
    return out.getvalue()


@override_settings(CLIP_ROOT=PHOTO_DIR)
class PhotoShrinkTests(TestCase):
    """T77: a phone photo is stored upright, at most 1600 px, as a small JPEG with no EXIF."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("s@example.com", "s@example.com")
        self.trip = Trip.objects.create(user=self.user, destination="japan")
        self.client.force_login(self.user)

    def test_big_sideways_photo_is_turned_shrunk_and_stripped(self):
        from PIL import Image

        data = phone_jpeg()
        upload = SimpleUploadedFile("IMG_1.JPG", data, content_type="image/jpeg")
        self.client.post(reverse("there_add", args=["manhole"]), {"photo": upload})
        photo = Photo.objects.get()
        self.assertEqual(photo.content_type, "image/jpeg")
        self.assertTrue(photo.file.name.endswith(".jpg"))
        stored = Path(photo.file.path).read_bytes()
        self.assertEqual(photo.size, len(stored))
        self.assertLess(len(stored), 600 * 1024)
        img = Image.open(photo.file.path)
        # Orientation 6 means turn 90 degrees: the 4000x3000 file is a 3000x4000 upright photo.
        self.assertEqual(img.size, (1200, 1600))
        self.assertEqual(len(img.getexif()), 0)
        self.assertNotIn(b"Exif", stored[:4096])
        # After the turn the blue left half is on top.
        self.assertGreater(img.getpixel((600, 100))[2], 200)
        self.assertGreater(img.getpixel((600, 1500))[0], 200)
        r = self.client.get(reverse("photo", args=[photo.id]))
        self.assertEqual(r["Cache-Control"], "private, max-age=86400")

    def test_png_with_transparency_becomes_jpeg(self):
        import io

        from PIL import Image

        out = io.BytesIO()
        Image.new("RGBA", (800, 600), (0, 0, 0, 0)).save(out, "PNG")
        upload = SimpleUploadedFile("s.png", out.getvalue(), content_type="image/png")
        self.client.post(reverse("there_add", args=["pikachu"]), {"photo": upload})
        photo = Photo.objects.get()
        self.assertEqual(photo.content_type, "image/jpeg")
        self.assertEqual(Image.open(photo.file.path).size, (800, 600))

    def test_shrink_command_converts_old_photos(self):
        from django.core.files.base import ContentFile
        from PIL import Image

        photo = Photo.objects.create(trip=self.trip, thing="manhole", file=ContentFile(phone_jpeg(), name="old.jpg"))
        old = Path(photo.file.path)
        call_command("shrink_photos", stdout=open("/dev/null", "w"))
        photo.refresh_from_db()
        self.assertFalse(old.exists())
        self.assertEqual(Image.open(photo.file.path).size, (1200, 1600))
        self.assertEqual(photo.size, Path(photo.file.path).stat().st_size)
