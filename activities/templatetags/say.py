import re
from functools import lru_cache
from pathlib import Path

import yaml
from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


def _countries(country):
    """The asked country first, then every other content country. A template asks with the default
    country (japan); the Uzbek words (T171) are found in the next one."""
    others = sorted(p.name for p in (Path(settings.BASE_DIR) / "content").iterdir() if p.is_dir() and p.name != country)
    return [country] + others


@lru_cache(maxsize=256)
def _audio(reading, country):
    if not reading:
        return ""
    for c in _countries(country):
        path = f"audio/{c}/{reading}.mp3"
        if finders.find(path):
            return static(path)
    return ""


@lru_cache(maxsize=1)
def _photo_credits():
    from content_admin.loader import load_photo_credits
    return load_photo_credits()


@register.filter
def photo_credit(credit_id):
    """The credit entry (author, licence, source_url) of a content photo, or None (T159)."""
    return _photo_credits().get(str(credit_id or ""))


@register.filter
def word_audio(reading, country="japan"):
    """URL of the pre-made mp3 for a word (deploy/make_word_audio.py), or '' when none exists."""
    return _audio(str(reading or ""), country)


def _key(text):
    return re.sub(r"[\s!?.,׳']+$", "", text.strip()).lower()


@lru_cache(maxsize=8)
def _hebrew(country):
    """Hebrew spelling -> reading, from every content item whose English label or title is the reading itself
    (a flip card 'Ohayou' / 'אוהאיו', the food card 'Itadakimasu!' / 'איטדקימס!')."""
    out = {}

    def walk(node):
        if isinstance(node, dict):
            reading = node.get("reading")
            if isinstance(reading, str):
                for en, he in (("label", "label_he"), ("title", "title_he")):
                    if isinstance(node.get(en), str) and isinstance(node.get(he), str) and _key(node[en]) == reading.lower():
                        out.setdefault(_key(node[he]), reading)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in sorted((Path(settings.BASE_DIR) / "content" / country).glob("*.yaml")):
        walk(yaml.safe_load(path.read_text(encoding="utf-8")))
    return out


def _reading(word, country):
    key = _key(word)
    if _audio(key, country):
        return key
    for c in _countries(country):
        if key in _hebrew(c):
            return _hebrew(c)[key]
    return ""


def _span(word, reading, country):
    return (f'<span class="say-word say-inline" lang="ja" data-say="{escape(reading)}" '
            f'data-say-src="{_audio(reading, country)}" tabindex="0">{escape(word)}</span>')


QUOTED = re.compile(r'(["“״])([^"“”״]{2,40})(["”״])')
LEAD = re.compile(r"^([^:\"]{2,30})(:)")


@register.filter
def say_quoted(text, country="japan"):
    """Text with each Japanese word that has an mp3 made tappable (T158): a word in quotes ('Say "itadakimasu"
    before you eat') or the word before the colon at the start of a tip ('Itadakimasu: before the first bite')."""
    text = str(text or "")
    out, pos = [], 0
    lead = LEAD.match(text)
    if lead and _reading(lead.group(1), country):
        out.append(_span(lead.group(1), _reading(lead.group(1), country), country))
        pos = lead.end(1)
    for m in QUOTED.finditer(text, pos):
        reading = _reading(m.group(2), country)
        if not reading:
            continue
        out.append(escape(text[pos:m.start(2)]))
        out.append(_span(m.group(2), reading, country))
        pos = m.end(2)
    out.append(escape(text[pos:]))
    return mark_safe("".join(out))
