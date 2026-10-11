"""T158: every Japanese word with an mp3 talks where it shows; 'itadakimasu' talks on every page."""
import re
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from activities.templatetags.say import say_quoted
from content_admin.models import Module
from courses.builder import build_course
from trips.models import Traveller, Trip

ITADAKIMASU = re.compile(r"itadakimasu|いただきます|איטדקימס", re.I)
SRC = "/static/audio/japan/itadakimasu.mp3"


class Silent(HTMLParser):
    """Collects each 'itadakimasu' text or picture in <main> that has no [data-say] around it with the mp3."""

    VOID = {"img", "br", "hr", "input", "meta", "link", "source"}

    def __init__(self):
        super().__init__()
        self.stack, self.silent, self.talks, self.main = [], [], 0, 0
        self.target = 0  # T162: a picture in the match game is a drop target; the word plate says the word when it lands

    def say_src(self):
        return next((s for _, s in reversed(self.stack) if s is not None), None)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "main":
            self.main += 1
        if tag == "img" and self.main and not self.target and "itadakimasu" in (a.get("src") or ""):
            (self.silent.append("IMG") if self.say_src() != SRC else None)
            self.talks += self.say_src() == SRC
        if tag not in self.VOID:
            self.stack.append((tag, a.get("data-say-src") if "data-say" in a else None))
            self.target += "match-target" in (a.get("class") or "").split()

    def handle_endtag(self, tag):
        if tag == "main":
            self.main -= 1
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                if tag == "button" and self.target:
                    self.target -= 1
                del self.stack[i:]
                break

    def handle_data(self, data):
        if not self.main or not ITADAKIMASU.search(data) or any(t in ("script", "style") for t, _ in self.stack):
            return
        if self.say_src() == SRC:
            self.talks += 1
        elif not re.search(r'["“״]\s*$|^\s*["”״]', data):
            # A sentence keeps its quotes outside the word span: 'Say "' + <span>itadakimasu</span> + '" before'.
            self.silent.append(data.strip()[:70])


def readings(node, out):
    if isinstance(node, dict):
        if node.get("japanese") and isinstance(node.get("reading"), str):
            out.add(node["reading"])
        for v in node.values():
            readings(v, out)
    elif isinstance(node, list):
        for v in node:
            readings(v, out)
    return out


class SayQuotedTests(TestCase):
    def test_a_quoted_word_with_an_mp3_talks(self):
        html = say_quoted('Say "itadakimasu" before you eat.')
        self.assertEqual(html, 'Say &quot;<span class="say-word say-inline" lang="ja" data-say="itadakimasu" '
                               f'data-say-src="{SRC}" tabindex="0">itadakimasu</span>&quot; before you eat.')

    def test_the_lead_word_of_a_tip_talks(self):
        self.assertIn(f'data-say-src="{SRC}" tabindex="0">Itadakimasu</span>: before', say_quoted("Itadakimasu: before the first bite."))

    def test_hebrew_spelling_talks(self):
        self.assertIn(f'data-say-src="{SRC}" tabindex="0">איטדקימס</span>', say_quoted('אומרים "איטדקימס" לפני האוכל.'))
        self.assertIn("audio/japan/ohayou.mp3", say_quoted('אומרים "אוהאיו" בבוקר.'))

    def test_other_quotes_stay_text_and_are_escaped(self):
        self.assertEqual(say_quoted('Say "gochisousama deshita" <b>'), 'Say &quot;gochisousama deshita&quot; &lt;b&gt;')
        self.assertEqual(say_quoted("Tip: no word here"), "Tip: no word here")


class EveryWordTalksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_content", verbosity=0)
        cls.user = get_user_model().objects.create_user("say@example.com", "say@example.com")
        trip = Trip.objects.create(user=cls.user, destination="japan")
        for age in (38, 4):
            Traveller.objects.create(trip=trip, age=age)
        cls.course = build_course(trip, list(Module.objects.filter(country="japan", ready=True).values_list("id", flat=True)))

    def pages(self):
        self.client.force_login(self.user)
        for item in self.course.items.select_related("activity"):
            for lang in ("en", "he"):
                r = self.client.get(reverse("activity", args=[item.id]) + f"?lang={lang}")
                if r.status_code == 200:
                    yield item, lang, r.content.decode()

    def test_every_reading_has_an_mp3_and_a_say_word(self):
        missing, silent, n = [], [], 0
        for item, lang, html in self.pages():
            for reading in sorted(readings(item.activity.data, set())):
                if not finders.find(f"audio/japan/{reading}.mp3"):
                    missing.append(reading)
                    continue
                n += 1
                if f'data-say-src="{static(f"audio/japan/{reading}.mp3")}"' not in html:
                    silent.append(f"{item.activity.slug} {lang} {reading}")
        self.assertGreater(n, 50)
        self.assertEqual(sorted(set(missing)), ["ichi, ni, san", "watashi wa … desu"], "run deploy/make_word_audio.py")
        self.assertEqual(silent, [])

    def test_itadakimasu_talks_on_every_page_where_it_shows(self):
        seen, silent = [], []
        for item, lang, html in self.pages():
            p = Silent()
            p.feed(html)
            if p.talks or p.silent:
                seen.append(f"{item.activity.slug} {lang}")
            silent += [f"{item.activity.slug} {lang}: {s}" for s in p.silent]
        self.assertEqual(silent, [])
        for slug in ("words-lesson", "food-cards", "sushi-lesson", "manners-lesson"):
            self.assertIn(f"{slug} en", seen)
            self.assertIn(f"{slug} he", seen)
