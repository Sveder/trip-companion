"""T229: production static URLs carry a content hash, so nginx can cache /static/ for a year."""
import re
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from activities.templatetags import say
from content_admin.models import Activity, Module
from courses.builder import build_course
from trips.models import Traveller, Trip

HASHED = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "tripapp.storage.HashedStaticStorage"},
}
# /static/css/app.3f2a91c0b1d4.css: a 12-character hex hash before the extension.
HASH = re.compile(r"\.[0-9a-f]{12}\.[a-z0-9]+$")


class HashedStaticUrls(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="t229-")
        cls.override = override_settings(STORAGES=HASHED, STATIC_ROOT=cls.root)
        cls.override.enable()
        call_command("collectstatic", "--noinput", verbosity=0)
        say._audio.cache_clear()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        say._audio.cache_clear()
        shutil.rmtree(cls.root, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        call_command("load_content", "japan", verbosity=0)
        cls.user = get_user_model().objects.create_user("h@example.com", "h@example.com")
        cls.trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (40, 5):
            Traveller.objects.create(trip=cls.trip, age=age)
        cls.course = build_course(cls.trip, list(Module.objects.filter(country="japan").values_list("id", flat=True)))

    def static_urls(self, path):
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200, path)
        return re.findall(r"/static/[^\"']+", r.content.decode())

    def test_lesson_words_and_course_pages_use_hashed_names(self):
        self.client.force_login(self.user)
        sushi = self.course.items.get(activity=Activity.objects.get(module__slug="food", slug="sushi-lesson"))
        words = self.course.items.filter(activity__module__slug="words").first()
        pages = [reverse("activity", args=[sushi.id]), reverse("activity", args=[words.id]), "/"]
        seen = 0
        for page in pages:
            for lang in ("en", "he"):
                for url in self.static_urls(f"{page}?lang={lang}"):
                    self.assertRegex(url.split("?")[0], HASH, (page, lang, url))
                    seen += 1
        # The sushi lesson alone has dozens of pictures; the words page has the mp3 files.
        self.assertGreater(seen, 50)
        self.assertTrue(any(u.endswith(".mp3") for u in self.static_urls(reverse("activity", args=[words.id]))))

    def test_css_fonts_point_at_hashed_files(self):
        css = next(Path(self.root, "css").glob("app.*.css")).read_text()
        fonts = re.findall(r'url\("(\.\./fonts/[^"]+)"\)', css)
        self.assertTrue(fonts)
        for f in fonts:
            self.assertRegex(f, HASH)

    def test_500_page_links_the_hashed_css(self):
        from django.template import loader
        html = loader.get_template("500.html").render()
        self.assertRegex(html, r'href="/static/css/app\.[0-9a-f]{12}\.css"')


class DevStaticUrls(TestCase):
    def test_tests_and_dev_keep_plain_names(self):
        self.assertEqual(settings.STORAGES["staticfiles"]["BACKEND"], "django.contrib.staticfiles.storage.StaticFilesStorage")
