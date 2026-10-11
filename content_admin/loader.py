"""Read the YAML content files into Module and Activity rows."""
from pathlib import Path

import yaml
from django.conf import settings
from django.db import transaction

from .models import Activity, Module

CONTENT_DIR = Path(settings.BASE_DIR) / "content"
MODULE_FIELDS = ("title", "summary", "title_he", "summary_he", "emoji", "audience", "order", "ready")


def module_files(country, content_dir=None):
    return sorted(Path(content_dir or CONTENT_DIR, country).glob("*.yaml"))


@transaction.atomic
def load_country(country, content_dir=None, force=False, log=None):
    """Create or update every module of one country. Returns the number of modules loaded.

    A module that Michael changed in the admin (``edited``) is left alone, so a deploy does not
    throw his edits away; ``export_content`` writes them to the YAML file first. ``force`` loads
    every file.
    """
    log = log or (lambda msg: None)
    count = 0
    for path in module_files(country, content_dir):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        slug = doc.get("id") or path.stem
        current = Module.objects.filter(country=country, slug=slug).first()
        if current and current.edited and not force:
            log(f"skip {country}/{slug}: changed in the admin; run export_content first, or --force")
            continue
        defaults = {k: doc[k] for k in MODULE_FIELDS if k in doc}
        defaults["edited"] = False
        was_stub = bool(current and not current.ready)
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
        log(f"load {country}/{slug}")
        count += 1
    add_new_activities(country, log)
    return count


def add_new_activities(country, log):
    """A new activity in a module (e.g. a lesson) joins every course that has that module.

    The course is rebuilt from its own module list; a rebuild keeps the done marks.
    A course with no new activity only gets the current order, in place.
    """
    from courses.builder import build_course, reorder_course
    from courses.models import Course

    for course in Course.objects.filter(trip__destination=country).select_related("trip"):
        have = set(course.items.values_list("activity_id", flat=True))
        want = set(Activity.objects.filter(module_id__in=course.module_ids).values_list("id", flat=True))
        if want - have:
            build_course(course.trip, course.module_ids)
            log(f"course {course.id}: {len(want - have)} new activities added")
        elif reorder_course(course):
            # The content order changed (e.g. a lesson moved first): the items keep their ids.
            log(f"course {course.id}: items put in the new order")


def load_previews():
    path = CONTENT_DIR / "previews.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_photo_credits():
    """The free-licence photo credits (trip-companion-tools/commons_photo.py writes the file), keyed by id."""
    path = CONTENT_DIR / "photo_credits.yaml"
    if not path.exists():
        return {}
    return {e["id"]: e for e in yaml.safe_load(path.read_text(encoding="utf-8")) or []}
