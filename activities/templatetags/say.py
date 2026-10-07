from functools import lru_cache

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@lru_cache(maxsize=256)
def _audio(reading, country):
    path = f"audio/{country}/{reading}.mp3"
    return static(path) if reading and finders.find(path) else ""


@register.filter
def word_audio(reading, country="japan"):
    """URL of the pre-made mp3 for a word (deploy/make_word_audio.py), or '' when none exists."""
    return _audio(str(reading or ""), country)
