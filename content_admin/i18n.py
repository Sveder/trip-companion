"""Hebrew content lives next to the English in the YAML: ``title`` and ``title_he``, ``text`` and ``text_he``.

``localize`` returns the content for the active language: in Hebrew a key takes its ``_he`` value when
there is one, else it keeps the English. The ``_he`` keys themselves are dropped in both languages.
"""
from django.utils.translation import get_language

SUFFIX = "_he"


def is_hebrew():
    return (get_language() or "").startswith("he")


def localize(value, hebrew=None):
    if hebrew is None:
        hebrew = is_hebrew()
    if isinstance(value, list):
        return [localize(v, hebrew) for v in value]
    if isinstance(value, dict):
        out = {}
        for key, v in value.items():
            if isinstance(key, str) and key.endswith(SUFFIX):
                continue
            if hebrew and value.get(f"{key}{SUFFIX}") not in (None, ""):
                v = value[f"{key}{SUFFIX}"]
            out[key] = localize(v, hebrew)
        return out
    return value
