import json
import shutil
import tempfile
from pathlib import Path

import yaml
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from courses.models import Course, CourseItem
from trips.models import Traveller, Trip

from .exporter import export_country
from .loader import CONTENT_DIR, load_country
from .models import Activity, Module


def snapshot():
    """Every module and activity as plain data, to compare two loads."""
    return [
        (m.slug, m.title, m.summary, m.emoji, m.audience, m.order, m.ready,
         [(a.slug, a.title, a.type, a.order, a.data) for a in m.activities.order_by("order", "slug")])
        for m in Module.objects.filter(country="japan").order_by("slug")
    ]


class ExportTests(TestCase):
    def setUp(self):
        call_command("load_content", verbosity=0)
        self.tmp = Path(tempfile.mkdtemp(prefix="trip-export-"))
        shutil.copytree(CONTENT_DIR / "japan", self.tmp / "japan")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_export_of_unchanged_content_changes_no_file(self):
        self.assertEqual(export_country("japan", self.tmp), [])

    def test_export_load_round_trip(self):
        food = Activity.objects.get(slug="food-cards")
        food.data["cards"][0]["text"] = "Sushi is rice with fish on top."
        food.save()
        before = snapshot()
        changed = export_country("japan", self.tmp)
        self.assertEqual([p.name for p in changed], ["food.yaml"])
        Activity.objects.filter(slug="food-cards").update(data={})  # spoil the database
        load_country("japan", content_dir=self.tmp, force=True)
        self.assertEqual(snapshot(), before)

    def test_export_keeps_the_comments(self):
        steps = Activity.objects.get(slug="chopsticks-intro")
        steps.data["steps"][1]["approved"] = True
        steps.save()
        export_country("japan", self.tmp)
        text = (self.tmp / "japan" / "chopsticks.yaml").read_text(encoding="utf-8")
        self.assertIn("# Only Michael approves a video.", text)
        self.assertIn("approved: true", text)
        source = (CONTENT_DIR / "japan" / "chopsticks.yaml").read_text(encoding="utf-8")
        self.assertEqual(text, source.replace("approved: false", "approved: true"))

    def test_export_writes_a_new_module_file(self):
        Module.objects.create(country="japan", slug="onsen", title="Hot springs", order=99)
        export_country("japan", self.tmp)
        doc = yaml.safe_load((self.tmp / "japan" / "onsen.yaml").read_text(encoding="utf-8"))
        self.assertEqual(doc["title"], "Hot springs")


class LoadProtectionTests(TestCase):
    def setUp(self):
        call_command("load_content", verbosity=0)

    def test_load_skips_a_module_changed_in_the_admin(self):
        Module.objects.filter(slug="food").update(title="Food we love", edited=True)
        call_command("load_content", verbosity=0, stderr=open("/dev/null", "w"))
        self.assertEqual(Module.objects.get(slug="food").title, "Food we love")
        call_command("load_content", "--force", verbosity=0)
        self.assertEqual(Module.objects.get(slug="food").title, "Japanese food")

    def test_export_clears_the_edited_mark(self):
        Module.objects.filter(slug="food").update(edited=True)
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(CONTENT_DIR / "japan", tmp / "japan")
            export_country("japan", tmp)
        finally:
            shutil.rmtree(tmp)
        self.assertFalse(Module.objects.get(slug="food").edited)


class AdminEditTests(TestCase):
    def setUp(self):
        call_command("load_content", verbosity=0)
        User = get_user_model()
        call_command("make_superuser", "boss@example.com", stdout=open("/dev/null", "w"))
        self.boss = User.objects.get(email="boss@example.com")
        self.family = User.objects.create_user("f@example.com", "f@example.com")
        trip = Trip.objects.create(user=self.family, destination="japan")
        Traveller.objects.create(trip=trip, age=4)
        course = Course.objects.create(trip=trip)
        self.item = CourseItem.objects.create(course=course, order=0, activity=Activity.objects.get(slug="food-cards"))

    def test_make_superuser_has_no_password(self):
        self.assertTrue(self.boss.is_superuser and self.boss.is_staff)
        self.assertFalse(self.boss.has_usable_password())

    def test_admin_login_goes_to_the_email_code_page(self):
        r = self.client.get(reverse("admin:login") + "?next=/admin/")
        self.assertRedirects(r, reverse("signin") + "?next=%2Fadmin%2F", fetch_redirect_response=False)
        self.client.force_login(self.family)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.assertRedirects(self.client.get(reverse("admin:login")), reverse("home"), fetch_redirect_response=False)

    def test_signin_passes_next_to_the_code_page(self):
        r = self.client.post(reverse("signin") + "?next=/admin/", {"email": "boss@example.com"})
        self.assertEqual(r["Location"], reverse("account_confirm_login_code") + "?next=%2Fadmin%2F")
        r = self.client.post(reverse("signin") + "?next=https://evil.example/", {"email": "boss@example.com"})
        self.assertEqual(r["Location"], reverse("account_confirm_login_code"))

    def test_admin_edit_changes_the_rendered_page(self):
        act = Activity.objects.get(slug="food-cards")
        self.client.force_login(self.boss)
        url = reverse("admin:content_admin_activity_change", args=[act.pk])
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        form = page.context["adminform"].form
        post = {name: form[name].value() for name in form.fields}
        data = dict(act.data)
        data["cards"] = [dict(data["cards"][0], text="Sushi is a small treat of rice and fish.")] + data["cards"][1:]
        post["data"] = json.dumps(data)
        post["module"] = act.module_id
        r = self.client.post(url, post)
        self.assertEqual(r.status_code, 302, r.content[:2000])
        self.assertTrue(Module.objects.get(slug="food").edited)
        self.client.force_login(self.family)
        html = self.client.get(reverse("activity", args=[self.item.id])).content.decode()
        self.assertIn("Sushi is a small treat of rice and fish.", html)

    def test_activity_list_shows_video_approval(self):
        self.client.force_login(self.boss)
        html = self.client.get(reverse("admin:content_admin_activity_changelist")).content.decode()
        self.assertIn("CBNw5yX1M34 (not approved)", html)
