"""Write the Module and Activity rows back to the YAML content files.

The writer edits the existing file in place (ruamel round-trip), so the comments and the
quoting in the file stay where they are; only the values that changed are rewritten.
"""
import io
from pathlib import Path

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .loader import module_files
from .models import Module


def module_doc(module):
    """The content of one module as the plain dict that its YAML file holds."""
    doc = {
        "id": module.slug,
        "title": module.title,
        "summary": module.summary,
        "emoji": module.emoji,
        "audience": module.audience,
        "order": module.order,
        "ready": module.ready,
        "activities": [],
    }
    for index, act in enumerate(module.activities.order_by("order", "slug")):
        entry = {"id": act.slug, "title": act.title, "type": act.type}
        if act.order != index:
            entry["order"] = act.order
        entry.update(act.data)
        doc["activities"].append(entry)
    return doc


def merge(old, new):
    """Put the values of ``new`` into the ruamel tree ``old`` and keep its comments and styles."""
    if isinstance(old, CommentedMap) and isinstance(new, dict):
        for key in [k for k in old if k not in new]:
            del old[key]
        for key, value in new.items():
            old[key] = merge(old[key], value) if key in old else value
        return old
    if isinstance(old, CommentedSeq) and isinstance(new, list):
        for i, value in enumerate(new):
            if i < len(old):
                old[i] = merge(old[i], value)
            else:
                old.append(value)
        del old[len(new):]
        return old
    if old == new and isinstance(old, bool) == isinstance(new, bool):
        return old  # same value: keep the quoting of the file
    return new


def _yaml():
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def export_country(country, content_dir, log=None):
    """Write every module of one country to <content_dir>/<country>/<file>.yaml. Returns the paths changed."""
    log = log or (lambda msg: None)
    y = _yaml()
    out_dir = Path(content_dir, country)
    out_dir.mkdir(parents=True, exist_ok=True)
    by_slug = {}
    for path in module_files(country, content_dir):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        by_slug[doc.get("id") or path.stem] = path
    changed = []
    for module in Module.objects.filter(country=country).prefetch_related("activities"):
        new = module_doc(module)
        path = by_slug.get(module.slug, out_dir / f"{module.slug}.yaml")
        old_text = path.read_text(encoding="utf-8") if path.exists() else ""
        tree = y.load(old_text) if old_text else None
        if tree is not None and "id" not in tree and path.stem == module.slug:
            new.pop("id")  # the file name gives the id
        if tree is None or yaml.safe_load(old_text) != new:
            buf = io.StringIO()
            y.dump(merge(tree, new) if tree is not None else new, buf)
            path.write_text(buf.getvalue(), encoding="utf-8")
            changed.append(path)
            log(f"wrote {path}")
        Module.objects.filter(pk=module.pk).update(edited=False)
    return changed
