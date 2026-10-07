"""Read the YAML content files into Module and Activity rows."""
from pathlib import Path

import yaml
from django.conf import settings
from django.db import transaction

from .models import Activity, Module

CONTENT_DIR = Path(settings.BASE_DIR) / "content"
MODULE_FIELDS = ("title", "summary", "emoji", "audience", "order", "ready")


def module_files(country):
    return sorted((CONTENT_DIR / country).glob("*.yaml"))


@transaction.atomic
def load_country(country):
    """Create or update every module of one country. Returns the module count."""
    count = 0
    for path in module_files(country):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        slug = doc.get("id") or path.stem
        defaults = {k: doc[k] for k in MODULE_FIELDS if k in doc}
        was_stub = Module.objects.filter(country=country, slug=slug, ready=False).exists()
        module, _ = Module.objects.update_or_create(country=country, slug=slug, defaults=defaults)
        seen = []
        for index, act in enumerate(doc.get("activities", [])):
            act = dict(act)
            act_slug = act.pop("id")
            seen.append(act_slug)
            Activity.objects.update_or_create(
                module=module,
                slug=act_slug,
                defaults={
                    "title": act.pop("title"),
                    "type": act.pop("type"),
                    "order": act.pop("order", index),
                    "data": act,
                },
            )
        module.activities.exclude(slug__in=seen).delete()
        if was_stub and module.ready:
            # A "coming soon" stub became a real module: families who pressed past the stub must see it.
            from courses.models import CourseItem

            CourseItem.objects.filter(activity__module=module).update(done_at=None)
        count += 1
    return count


def load_previews():
    path = CONTENT_DIR / "previews.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))
