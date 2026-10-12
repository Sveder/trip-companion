"""T191: the security review (devpost/security-review.md). Each test pins one check of the report."""
import tempfile

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.link import link_token
from accounts.views import make_account
from activities.models import Clip
from courses.builder import build_course, suggestions
from reminders.models import Contact
from there.models import Photo
from trips.models import Traveller, Trip

from .redact import RedactingLogger, redact, scrub_event

FILE_DIR = tempfile.mkdtemp(prefix="trip-sec-")
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200


def photo():
    return SimpleUploadedFile("p.jpg", JPEG, content_type="image/jpeg")


def clip():
    return SimpleUploadedFile("c.webm", b"\x1aE\xdf\xa3fakewebm", content_type="video/webm")


class SignInSpamTests(TestCase):
    """The old sign-in page made an account for any address and mailed it a code, with no limit."""

    def setUp(self):
        cache.clear()

    def test_unknown_address_gets_no_mail_and_no_account(self):
        before = get_user_model().objects.count()
        r = self.client.post(reverse("signin"), {"email": "stranger@example.com"})
        self.assertEqual(r.status_code, 302)  # the same code page as a known address: no account check from outside
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(get_user_model().objects.count(), before)

    def test_known_address_gets_a_code(self):
        make_account("boss@example.com")
        self.client.post(reverse("signin"), {"email": "boss@example.com"})
        self.assertEqual(len(mail.outbox), 1)

    def test_one_address_gets_at_most_three_codes_an_hour(self):
        make_account("boss@example.com")
        codes = [self.client_class().post(reverse("signin"), {"email": "boss@example.com"}).status_code for _ in range(5)]
        self.assertEqual(codes, [302, 302, 302, 429, 429])
        self.assertEqual(len(mail.outbox), 3)

    def test_one_ip_address_asks_at_most_ten_times_an_hour(self):
        codes = [self.client_class().post(reverse("signin"), {"email": f"x{n}@example.com"}, HTTP_X_REAL_IP="203.0.113.9").status_code
                 for n in range(12)]
        self.assertEqual(codes[:10], [302] * 10)
        self.assertEqual(codes[10:], [429, 429])
        # Another address is not blocked by that one.
        r = self.client.post(reverse("signin"), {"email": "y@example.com"}, HTTP_X_REAL_IP="203.0.113.10")
        self.assertEqual(r.status_code, 302)

    def test_continue_mail_is_limited_per_ip(self):
        codes = [self.client_class().post(reverse("continue"), {"email": f"f{n}@example.com"}, HTTP_X_REAL_IP="203.0.113.7").status_code
                 for n in range(11)]
        self.assertEqual(codes[-1], 429)
        self.assertEqual(len(mail.outbox), 10)


class LinkTokenTests(TestCase):
    def test_token_is_long_random_and_url_safe(self):
        tokens = set()
        for n in range(20):
            user = get_user_model().objects.create_user(f"family-{n}")
            tokens.add(link_token(Contact.objects.create(user=user)))
        self.assertEqual(len(tokens), 20)
        for t in tokens:
            self.assertGreaterEqual(len(t), 43)  # 32 random bytes = 256 bits
            self.assertRegex(t, r"^[A-Za-z0-9_-]+$")

    def test_a_wrong_token_opens_nothing(self):
        user = get_user_model().objects.create_user("family-a")
        token = link_token(Contact.objects.create(user=user))
        r = self.client.get(reverse("continue_open", args=[token[:-1] + ("A" if token[-1] != "A" else "B")]))
        self.assertEqual(r.status_code, 404)
        self.assertNotIn("_auth_user_id", self.client.session)


class TokenNotLoggedTests(TestCase):
    TOKEN = "Zk3v9Q_secret-token-1234567890abcdefghijklmno"

    def test_redact_hides_the_link_and_stop_tokens(self):
        self.assertEqual(redact(f"GET /continue/{self.TOKEN}/ HTTP/1.1"), "GET /continue/<token>/ HTTP/1.1")
        self.assertEqual(redact(f"https://trip.sveder.com/reminders/stop/{self.TOKEN}/"),
                         "https://trip.sveder.com/reminders/stop/<token>/")
        self.assertEqual(redact("/continue/"), "/continue/")  # the form page stays readable

    def test_gunicorn_access_log_has_no_token(self):
        class Req:
            headers = [("REFERER", f"https://trip.sveder.com/continue/{TokenNotLoggedTests.TOKEN}/")]

        class Resp:
            status, headers, sent, response_length = "302 Found", [], 0, 0

        class Cfg:
            def __getattr__(self, name):
                return None

        logger = RedactingLogger.__new__(RedactingLogger)
        logger.cfg = Cfg()
        from datetime import timedelta
        atoms = logger.atoms(Resp(), Req(), {"REMOTE_ADDR": "1.2.3.4", "REQUEST_METHOD": "GET", "RAW_URI": f"/continue/{self.TOKEN}/",
                              "PATH_INFO": f"/continue/{self.TOKEN}/", "SERVER_PROTOCOL": "HTTP/1.1",
                              "HTTP_REFERER": f"https://x/continue/{self.TOKEN}/"},
                             timedelta(seconds=0.1))
        self.assertNotIn(self.TOKEN, " ".join(str(v) for v in atoms.values()))
        self.assertEqual(atoms["r"], "GET /continue/<token>/ HTTP/1.1")

    def test_sentry_event_has_no_token(self):
        event = {"transaction": f"/continue/{self.TOKEN}/",
                 "request": {"url": f"https://trip.sveder.com/continue/{self.TOKEN}/", "headers": {"Referer": f"/continue/{self.TOKEN}/"}},
                 "breadcrumbs": {"values": [{"message": f"GET /continue/{self.TOKEN}/", "data": {"url": f"/continue/{self.TOKEN}/"}}]}}
        self.assertNotIn(self.TOKEN, repr(scrub_event(event)))


@override_settings(CLIP_ROOT=FILE_DIR)
class FamilyDataTests(TestCase):
    """No IDOR: every URL with an id answers 404 to another family. Uploads are capped and served safely."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)

    def family(self, name):
        user = get_user_model().objects.create_user(name)
        trip = Trip.objects.create(user=user, destination="japan")
        Traveller.objects.create(trip=trip, age=6)
        build_course(trip, [m.id for m, on in suggestions(trip) if on])
        return user, trip

    def setUp(self):
        self.a, self.trip_a = self.family("family-a")
        self.b, _ = self.family("family-b")
        self.item = self.trip_a.course.items.first()
        self.client.force_login(self.a)
        self.client.post(reverse("there_add", args=["vending"]), {"photo": photo()})
        self.client.post(reverse("clip_save", args=[self.item.id]), {"clip": clip()})
        self.photo = Photo.objects.get(trip=self.trip_a)
        self.clip = Clip.objects.get(trip=self.trip_a)

    def test_another_family_gets_404_everywhere(self):
        other = self.client_class()
        other.force_login(self.b)
        gets = [reverse("activity", args=[self.item.id]), reverse("activity_praise", args=[self.item.id]),
                reverse("clip", args=[self.clip.id]), reverse("photo", args=[self.photo.id]),
                reverse("go", args=[self.item.id, "x"])]
        posts = [reverse("activity_done", args=[self.item.id]), reverse("clip_save", args=[self.item.id]),
                 reverse("photo_delete", args=[self.photo.id]), reverse("track_video", args=[self.item.id])]
        for url in gets:
            self.assertEqual(other.get(url).status_code, 404, url)
        for url in posts:
            self.assertEqual(other.post(url).status_code, 404, url)
        self.assertTrue(Photo.objects.filter(id=self.photo.id).exists())
        # state.json takes no id: a new family with no trip gets an empty copy, never family A's trip.
        self.assertIsNone(self.client_class().get(reverse("state_json")).json()["trip"])

    def test_own_files_are_served_as_files_that_run_nothing(self):
        for url in (reverse("photo", args=[self.photo.id]), reverse("clip", args=[self.clip.id])):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertIn("sandbox", r["Content-Security-Policy"])
            self.assertEqual(r["Content-Disposition"], "inline")
            self.assertIn(r["Content-Type"], ("image/jpeg", "video/webm"))

    def test_html_and_svg_uploads_are_refused(self):
        bad = SimpleUploadedFile("x.svg", b"<svg onload=alert(1)>", content_type="image/svg+xml")
        self.assertEqual(self.client.post(reverse("there_add", args=["vending"]), {"photo": bad}).status_code, 400)
        bad = SimpleUploadedFile("x.html", b"<script>", content_type="text/html")
        self.assertEqual(self.client.post(reverse("clip_save", args=[self.item.id]), {"clip": bad}).status_code, 400)

    @override_settings(PHOTO_MAX_PER_TRIP=1, CLIP_MAX_PER_TRIP=1)
    def test_uploads_are_capped_per_trip(self):
        self.assertEqual(self.client.post(reverse("there_add", args=["vending"]), {"photo": photo()}).status_code, 400)
        self.assertEqual(self.client.post(reverse("clip_save", args=[self.item.id]), {"clip": clip()}).status_code, 400)
        self.assertEqual(Photo.objects.filter(trip=self.trip_a).count(), 1)


class HeaderTests(TestCase):
    def test_every_page_has_a_safe_content_security_policy(self):
        r = self.client.get(reverse("privacy"))
        csp = r["Content-Security-Policy"]
        for rule in ("object-src 'none'", "base-uri 'self'", "frame-ancestors 'none'"):
            self.assertIn(rule, csp)

    def test_production_settings_pass_check_deploy(self):
        import subprocess
        import sys

        from django.conf import settings
        env = {"DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": "x" * 30 + "Ab1!" * 10, "PATH": "/usr/bin:/bin"}
        out = subprocess.run([sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
                             cwd=settings.BASE_DIR, env=env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_debug_is_off_and_secret_from_env_in_production(self):
        from pathlib import Path

        settings_py = (Path(__file__).parent / "settings.py").read_text()
        self.assertIn('DEBUG = env_bool("DJANGO_DEBUG"', settings_py)
        self.assertIn('os.environ.get("DJANGO_SECRET_KEY"', settings_py)
        self.assertIn('raise ImproperlyConfigured("Set DJANGO_SECRET_KEY', settings_py)
        self.assertNotIn("csrf_exempt", "".join(p.read_text() for p in Path(__file__).parent.parent.glob("*/*.py")
                                                    if not p.name.startswith("test")))
