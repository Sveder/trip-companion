from django.test import TestCase, override_settings


class TvModeTests(TestCase):
    def test_off_by_default(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn('class="tv"', html)
        self.assertIn("js/tv.js", html)

    def test_query_turns_it_on_and_the_session_keeps_it(self):
        self.assertIn('<html lang="en" dir="ltr" class="tv">', self.client.get("/?tv=1").content.decode())
        self.assertIn('class="tv"', self.client.get("/").content.decode())
        self.assertNotIn('class="tv"', self.client.get("/?tv=0").content.decode())
        self.assertNotIn('class="tv"', self.client.get("/").content.decode())

    def test_lg_webos_browser_gets_tv_mode(self):
        ua = "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0 Safari/537.36 WebAppManager"
        self.assertIn('class="tv"', self.client.get("/", HTTP_USER_AGENT=ua).content.decode())

    def test_lg_tv_browser_from_the_real_tv_gets_tv_mode(self):
        # The exact User-Agent of Michael's LG 55UP7550PVG browser (webOS 6), from the server log 2026-10-08.
        ua = ("Mozilla/5.0 (Linux; NetCast; U) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/87.0.3945.79 Safari/537.36 SmartTV/10.0 Colt/2.0")
        self.assertIn('class="tv"', self.client.get("/", HTTP_USER_AGENT=ua).content.decode())

    def test_remote_can_reach_the_spoken_word(self):
        # T137: the arrows must reach the Japanese word on a lesson page, so OK can play it.
        import re
        from pathlib import Path
        from django.conf import settings
        base = Path(settings.BASE_DIR)
        js = (base / "static/js/tv.js").read_text()
        self.assertRegex(js, r"var SELECTOR = '[^']*\.say-word\[tabindex\]")
        lesson = (base / "templates/activities/lesson.html").read_text()
        words = re.findall(r'<[^>]*class="[^"]*say-word[^"]*"[^>]*>', lesson)
        self.assertTrue(words)
        for tag in words:
            self.assertIn('tabindex="0"', tag)
        self.assertIn(".tv .say-word:focus", (base / "static/css/app.css").read_text())

    def test_phone_browser_does_not(self):
        ua = "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"
        self.assertNotIn('class="tv"', self.client.get("/", HTTP_USER_AGENT=ua).content.decode())


class ProfessionalBasicsTests(TestCase):
    def test_styled_404(self):
        with self.settings(DEBUG=False):
            r = self.client.get("/does-not-exist")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "We can't find that page", status_code=404)
        self.assertContains(r, "app.css", status_code=404)

    def test_500_page_renders_without_context(self):
        from django.views.defaults import server_error
        from django.test import RequestFactory

        r = server_error(RequestFactory().get("/"))
        self.assertEqual(r.status_code, 500)
        self.assertIn("Something went wrong", r.content.decode())

    def test_privacy_page_and_footer_link(self):
        r = self.client.get("/privacy/")
        self.assertContains(r, "Delete your account")
        self.assertIn('href="/privacy/"', self.client.get("/").content.decode())
        # T55: the page names what the app keeps today, and it reads fully in Hebrew.
        self.assertContains(r, "Photos you take in Japan")
        self.assertContains(r, "how many kids and how many grown-ups")
        self.assertContains(r, "how many days")
        self.assertNotContains(r, "Videos")
        self.assertContains(r, 'href="mailto:m@sveder.com?subject=Delete%20my%20Trip%20Companion%20account"')
        he = self.client.get("/privacy/?lang=he").content.decode()
        for text in ("תמונות שאתם מצלמים ביפן", "כמה ילדים וכמה מבוגרים", "לכמה ימים", "מחיקת החשבון"):
            self.assertIn(text, he)
        self.assertIn('href="mailto:m@sveder.com?subject=Delete%20my%20Trip%20Companion%20account"', he)
        main = he.split('<article', 1)[1].split('</article>', 1)[0]
        self.assertNotRegex(main.replace("Trip Companion", "").replace("Sentry", "").replace("m@sveder.com", ""), r"(?i)>[^<]*\b(we|the|you|your)\b")

    def test_share_preview_tags(self):
        html = self.client.get("/").content.decode()
        for tag in ('property="og:title"', 'property="og:description"', 'property="og:image" content="https://trip.sveder.com/static/img/og-image.png"', 'name="twitter:card"'):
            self.assertIn(tag, html)

    def test_favicon(self):
        r = self.client.get("/favicon.ico")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/x-icon")

    def test_sentry_loader_only_when_set(self):
        self.assertNotIn("sentry-cdn", self.client.get("/").content.decode())
        with self.settings(SENTRY_JS_LOADER="https://js.sentry-cdn.com/abc.min.js"):
            self.assertIn('src="https://js.sentry-cdn.com/abc.min.js"', self.client.get("/").content.decode())


class SentryScopeTests(TestCase):
    def test_hand_run_commands_do_not_report(self):
        from tripapp.settings import sentry_wanted
        for cmd in ("shell", "dbshell", "test"):
            self.assertFalse(sentry_wanted(["manage.py", cmd, "-c", "raise RuntimeError(1)"]))
            self.assertFalse(sentry_wanted(["/srv/www/trip-companion/manage.py", cmd]))

    def test_gunicorn_and_cron_commands_report(self):
        from tripapp.settings import sentry_wanted
        self.assertTrue(sentry_wanted(["/srv/www/trip-companion/venv/bin/gunicorn", "tripapp.wsgi:application"]))
        self.assertTrue(sentry_wanted(["manage.py", "send_reminders"]))

    def test_check_route_is_staff_only(self):
        from django.contrib.auth import get_user_model
        self.assertEqual(self.client.get("/staff/sentry-check/").status_code, 404)
        staff = get_user_model().objects.create_user("s", "s@example.com", "x", is_staff=True)
        self.client.force_login(staff)
        with self.assertRaises(RuntimeError):
            self.client.get("/staff/sentry-check/")


class HeaderClearOfBadgeTests(TestCase):
    """The Sveder corner badge is fixed, 130 px, top right. The header must leave that corner free."""

    def test_header_padding_right_is_wider_than_the_badge(self):
        import re
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static/css/app.css").read_text()
        for rule in (r"\n\.top \{[^}]*\}", r"\n\.tv \.top \{[^}]*\}"):
            block = re.search(rule, css).group(0)
            right = int(re.search(r"padding: \S+ (\d+)px", block).group(1))
            self.assertGreaterEqual(right, 130, block)

    def test_phone_badge_scrolls_away_and_is_smaller(self):
        # T105: under 600 px the badge is 80 px and absolute, so the phone header pads 80 px or more.
        import re
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static/css/app.css").read_text()
        phone = css[css.index("T105: the header is ONE line"):]
        self.assertRegex(phone, r"html \.sv2 \{ position: absolute; --sv: 80px !important; \}")
        right = int(re.search(r"\.top \{[^}]*padding: \S+ (\d+)px", phone).group(1))
        self.assertGreaterEqual(right, 80)


    def test_tablet_header_puts_the_language_link_beside_sound(self):
        # T184: at 601-1279 px the language link wrapped to a row of its own. Row 1 is now brand, Sound on and the
        # language link; the nav is row 2 and stays inside the 140 px right padding, clear of the corner badge.
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static/css/app.css").read_text()
        block = css[css.index("@media (min-width: 601px) and (max-width: 1279px) {\n  .top-menu"):]
        block = block[:block.index("\n}\n")]
        self.assertIn(".top-menu { display: contents; }", block)
        self.assertIn(".top .sound-btn { order: 1; }", block)
        self.assertIn(".top .lang-switch { order: 2; }", block)
        self.assertRegex(block, r"\.top \.top-nav \{ order: 3; flex: 0 0 100%;")
        self.assertNotIn("margin-right: -", block)


class HeaderMenuTests(TestCase):
    """T105: a signed-in phone header folds the links behind one Menu button."""

    def test_signed_in_header_has_the_menu_button_and_the_links(self):
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user("m@example.com", "m@example.com", "pw-123456")
        from trips.models import Trip
        Trip.objects.create(user=u, destination="japan")
        self.client.force_login(u)
        html = self.client.get("/", follow=True).content.decode()
        self.assertIn('class="menu-btn link" aria-expanded="false" aria-controls="top-menu" aria-label="Menu"', html)
        self.assertIn('class="top-menu foldable" id="top-menu"', html)
        self.assertIn("Our adventure", html)
        self.client.cookies.load({"django_language": "he"})
        self.assertIn("תפריט", self.client.get("/", follow=True).content.decode())

    def test_signed_out_header_has_no_menu_button(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("menu-btn", html)
        self.assertIn('class="top-menu" id="top-menu"', html)
        self.assertIn("lang-switch", html)


class HeaderTripLinksTests(TestCase):
    """T210: the course, quiz and hunt links show only when they lead somewhere."""

    def nav(self, destination=None, lang="en"):
        import re
        from django.contrib.auth import get_user_model
        from trips.models import Trip
        u = get_user_model().objects.create_user(f"{destination}{lang}@example.com", "", "pw-123456")
        if destination:
            Trip.objects.create(user=u, destination=destination)
        self.client.force_login(u)
        self.client.cookies.load({"django_language": lang})
        html = self.client.get("/trip/").content.decode()
        return re.search(r'<nav class="top-nav">(.*?)</nav>', html, re.S).group(1)

    def test_no_trip_shows_no_course_quiz_or_hunt_link(self):
        from django.urls import reverse
        for lang in ("en", "he"):
            nav = self.nav(None, lang)
            for name in ("course", "quiz", "there"):
                self.assertNotIn(f'href="{reverse(name)}"', nav, (lang, name))
            self.assertIn(f'href="{reverse("trip_setup")}"', nav)

    def test_japan_trip_shows_all_three(self):
        from django.urls import reverse
        nav = self.nav("japan")
        for name in ("course", "quiz", "there"):
            self.assertIn(f'href="{reverse(name)}"', nav, name)
        self.assertIn("In Japan", nav)

    def test_uzbek_trip_shows_course_and_quiz_but_no_hunt(self):
        from django.urls import reverse
        nav = self.nav("uzbekistan")
        self.assertIn(f'href="{reverse("course")}"', nav)
        self.assertIn(f'href="{reverse("quiz")}"', nav)
        self.assertNotIn(f'href="{reverse("there")}"', nav)


class OldTvBrowserTests(TestCase):
    """The LG TV runs Chrome 87: no CSS aspect-ratio, no :has(), no Array.prototype.at (T101)."""

    def css(self):
        from pathlib import Path
        return (Path(__file__).resolve().parent.parent / "static/css/app.css").read_text()

    def test_pages_load_the_compat_script_and_the_at_polyfill(self):
        html = self.client.get("/").content.decode()
        self.assertIn("js/compat.js", html)
        self.assertIn("C.prototype.at", html)

    @override_settings(SENTRY_JS_LOADER="https://js.sentry-cdn.example/loader.min.js")
    def test_the_at_polyfill_runs_before_the_sentry_loader(self):
        # The loader pulls web-vitals, which calls .at() (TRIP-COMPANION-3, T126).
        html = self.client.get("/").content.decode()
        self.assertIn("loader.min.js", html)
        self.assertLess(html.index("C.prototype.at"), html.index("loader.min.js"))

    def test_boxes_that_hold_absolute_children_do_not_need_aspect_ratio(self):
        css = self.css()
        for sel in (".video-frame",):
            self.assertIn(sel + '::before { content: ""; display: block; padding-top:', css)
            rule = css.split("\n" + sel + " {", 1)[1].split("}", 1)[0]
            self.assertNotIn("aspect-ratio", rule)

    def test_every_has_checked_rule_has_a_class_twin(self):
        css = self.css()
        self.assertIn(".pick.on", css)
        for twin in (".module.on {", ".module.on .switch {", ".module.on .switch::after {", '[dir="rtl"] .module.on .switch::after'):
            self.assertIn(twin, css)


class HebrewFontTests(TestCase):
    """T151: Hebrew pages use Rubik, served from our own static files, not from Google."""

    def test_rubik_ships_with_its_licence_and_the_css_names_it(self):
        from pathlib import Path
        from django.conf import settings
        base = Path(settings.BASE_DIR) / "static"
        self.assertLess((base / "fonts/rubik-hebrew.woff2").stat().st_size, 40_000)
        self.assertIn("Rubik", (base / "fonts/OFL.txt").read_text())
        css = (base / "css/app.css").read_text()
        self.assertIn('url("../fonts/rubik-hebrew.woff2")', css)
        self.assertIn('[dir="rtl"] body, [lang="he"] { font-family: "Rubik"', css)
        self.assertNotIn("fonts.googleapis.com", css)

    def test_only_hebrew_pages_preload_the_font(self):
        self.assertNotContains(self.client.get("/privacy/"), "rubik-hebrew.woff2")
        self.client.cookies["django_language"] = "he"
        r = self.client.get("/privacy/")
        self.assertContains(r, 'dir="rtl"')
        self.assertContains(r, 'rel="preload" href="/static/fonts/rubik-hebrew.woff2"')
        self.assertNotContains(r, "fonts.googleapis.com")


class SpeakerMarkTests(TestCase):
    """T156: a word that talks shows a speaker mark, and a tap on a dot says the dot's word."""

    def read(self, rel):
        from pathlib import Path
        from django.conf import settings
        return (Path(settings.BASE_DIR) / rel).read_text()

    def test_css_marks_every_talking_word(self):
        css = self.read("static/css/app.css")
        for sel in ('.say-word[data-say-src]:not([data-say-src=""])::after',
                    '.card.word[data-say-src]:not([data-say-src=""]) .jp.small::after', ".say-mark", ".flip.playing .say-mark"):
            self.assertIn(sel, css)
        self.assertIn("margin-inline-start: .25em", css)

    def test_words_card_puts_the_mark_on_its_own_line(self):
        # T195: the words activity has the speaker under the kana on every card, and the kana never wraps.
        words = self.read("templates/activities/words.html")
        self.assertIn('<span class="say-mark word-say" aria-hidden="true"></span>', words)
        self.assertIn("{% if w.japanese|length >= 6 %} long{% endif %}", words)
        css = self.read("static/css/app.css")
        self.assertIn(".card.word .say-mark.word-say { display: block;", css)
        self.assertIn(".card.word .jp { white-space: nowrap; word-break: keep-all; }", css)
        self.assertIn(".words .card.word .jp { line-height: 2.6rem; }", css)

    def test_flip_card_uses_the_mark_not_the_emoji(self):
        lesson = self.read("templates/activities/lesson.html")
        self.assertIn('<span class="say-mark" aria-hidden="true"></span>', lesson)
        self.assertNotIn("flip-say", lesson)

    def test_game_kana_stays_on_one_line(self):
        # T236: a kana word on a pick choice, a flip card or a match plate never breaks; JS shrinks it to fit.
        css = self.read("static/css/app.css")
        self.assertIn(".choice-word .jp, .flip .jp, .match-plate .jp { white-space: nowrap; word-break: keep-all;", css)
        js = self.read("static/js/lesson.js")
        self.assertIn("var KANA = '.choice-word .jp, .flip .jp, .match-plate .jp';", js)
        self.assertIn("document.addEventListener('lpage-show', function (e) { fitKana(e.target); }, true);", js)

    def test_module_row_stays_on_one_line(self):
        # T238: a long module name ends in '...'; 'Activity N of M' never wraps to a second line. The TV keeps its row.
        css = self.read("static/css/app.css")
        self.assertIn(".progress > span:first-child:not(:last-of-type) { flex: 1 1 0; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }", css)
        self.assertIn(".progress > span + span { flex: none; white-space: nowrap; }", css)
        self.assertIn(".tv .progress > span:first-child { flex: 0 1 auto; }", css)
        self.assertIn('<span title="{{ module.local_title }}">', self.read("templates/activities/_frame.html"))

    def test_dot_tap_says_the_word(self):
        self.assertIn("window.tcSay = say", self.read("static/js/speak.js"))
        self.assertIn("classList.add('playing')", self.read("static/js/speak.js"))
        js = self.read("static/js/lesson.js")
        self.assertIn("querySelector('[data-say]')", js)
        self.assertIn("window.tcSay(word)", js)


class SoundToggleAndHintTests(TestCase):
    """T156 part B: a header Sound on/off toggle and a one-time 'tap a word' hint, in en and he."""

    def read(self, rel):
        from pathlib import Path
        from django.conf import settings
        return (Path(settings.BASE_DIR) / rel).read_text()

    def test_header_holds_the_toggle_and_the_hint_in_both_languages(self):
        html = self.client.get("/", follow=True).content.decode()
        self.assertIn('class="sound-btn link" aria-pressed="true" data-on="Sound on" data-off="Sound off"', html)
        self.client.cookies.load({"django_language": "he"})
        html = self.client.get("/", follow=True).content.decode()
        self.assertIn('data-on="צליל מופעל" data-off="צליל מושתק"', html)
        # T194: the hint left the base page; it sits in the flow of the pages with a talking word.
        from django.template.loader import render_to_string
        from django.utils import translation
        for lang, text in (("en", "Tap a Japanese word to hear it"), ("he", "לחצו על מילה ביפנית כדי לשמוע אותה")):
            with translation.override(lang):
                out = render_to_string("includes/say_tip.html", {})
                self.assertIn(text, out)
                self.assertNotIn("{#", out)
                self.assertNotIn("#}", out)

    def test_say_hint_sits_in_the_page_flow(self):
        # T194: fixed at the bottom it covered word cards and tips; under the header it covered the title (T174).
        css = self.read("static/css/app.css")
        rule = css[css.index(".say-tip { "):]
        rule = rule[:rule.index("}")]
        self.assertNotIn("position: fixed", rule)
        self.assertIn("max-height: 0", rule)
        self.assertNotIn("say-hint { position: fixed", css)
        self.assertNotIn("say-tip", self.read("templates/base.html"))
        for rel in ("templates/activities/_frame.html", "templates/activities/lesson.html",
                    "templates/practice/quiz.html", "templates/courses/highlights.html"):
            self.assertIn('{% include "includes/say_tip.html" %}', self.read(rel), rel)
        # The lesson puts it once, above the pages, not under the title as well.
        self.assertIn("{% block saytip %}{% endblock %}", self.read("templates/activities/lesson.html"))
        self.assertIn("querySelector('.say-tip')", self.read("static/js/speak.js"))

    def test_every_sound_obeys_the_toggle(self):
        speak = self.read("static/js/speak.js")
        self.assertIn("localStorage.getItem('tc_sound') !== '0'", speak)
        self.assertIn("if (!soundOn()) return;", speak)
        self.assertIn("localStorage.setItem('tc_hint_say', '1')", speak)
        self.assertIn("window.tcSoundOn()", self.read("static/js/celebrate.js"))


class SqliteLockSettingsTests(TestCase):
    """T178: two writers at the same second must wait, not fail with 'database is locked'."""

    def test_file_database_uses_wal_immediate_and_a_busy_timeout(self):
        import tempfile
        from django.conf import settings
        from django.db.backends.sqlite3.base import DatabaseWrapper
        cfg = dict(settings.DATABASES["default"])
        with tempfile.TemporaryDirectory() as d:
            cfg["NAME"] = f"{d}/t.sqlite3"
            conn = DatabaseWrapper(cfg, alias="t178")
            try:
                with conn.cursor() as c:
                    self.assertEqual(c.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                    self.assertEqual(c.execute("PRAGMA busy_timeout").fetchone()[0], 20000)
                self.assertEqual(conn.transaction_mode, "IMMEDIATE")
            finally:
                conn.close()


class SafetyCardTests(TestCase):
    """T277: the child safety card is made in the browser; the page has nothing that could send the data."""

    def test_page_renders_in_english_and_hebrew(self):
        en = self.client.get("/safety-card/")
        self.assertEqual(en.status_code, 200)
        self.assertContains(en, "Child safety card")
        self.assertContains(en, "js/safety_card.js")
        he = self.client.get("/safety-card/?lang=he").content.decode()
        self.assertIn("כרטיס בטיחות לילד", he)
        self.assertIn("הכול נשאר במכשיר הזה", he)

    def test_form_has_no_action_and_no_named_field(self):
        import re
        html = self.client.get("/safety-card/").content.decode()
        form = html[html.index("<form class=\"sc-form\""):html.index("</form>", html.index("<form class=\"sc-form\""))]
        self.assertNotIn("action=", form)
        self.assertNotIn("method=", form)
        self.assertNotIn("csrfmiddlewaretoken", form)
        self.assertEqual(re.findall(r"<(?:input|textarea|select)[^>]*\sname=", form), [])
        self.assertEqual(len(re.findall(r"<(?:input|textarea)", form)), 17)

    def test_script_sends_nothing_and_saves_nothing(self):
        from pathlib import Path
        from django.conf import settings
        js = (Path(settings.BASE_DIR) / "static/js/safety_card.js").read_text()
        for word in ("fetch(", "XMLHttpRequest", "sendBeacon", "localStorage", "sessionStorage", "indexedDB", ".submit("):
            self.assertNotIn(word, js, word)

    def test_safety_lesson_links_to_the_card(self):
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        from django.urls import reverse
        from content_admin.models import Activity
        from courses.builder import build_course
        from trips.models import Trip, Traveller
        call_command("load_content", verbosity=0)
        user = get_user_model().objects.create_user("s@example.com", "s@example.com")
        trip = Trip.objects.create(user=user, destination="japan")
        Traveller.objects.create(trip=trip, age=40)
        Traveller.objects.create(trip=trip, age=5)
        act = Activity.objects.get(module__slug="safety", slug="safety-lesson")
        item = build_course(trip, [act.module_id]).items.get(activity=act)
        self.client.force_login(user)
        for lang, text in (("en", "Print a child safety card"), ("he", "מדפיסים כרטיס בטיחות לילד")):
            html = self.client.get(reverse("activity", args=[item.id]) + f"?lang={lang}").content.decode()
            self.assertEqual(html.count('href="/safety-card/"'), 1, lang)
            self.assertIn(text, html)
        self.assertIn("The child safety card is made on your device", self.client.get("/privacy/?lang=en").content.decode())


class SafetyOverviewTests(TestCase):
    """T279 (Michael): a country overview page with the important safety things, linked from the adventure and the header."""

    def test_japan_page_has_numbers_koban_lost_plan_earthquake_and_card(self):
        en = self.client.get("/safety/japan/").content.decode()
        for text in ('href="tel:110"', 'href="tel:119"', "koban", "maigo desu", "get under a table", 'href="/safety-card/"'):
            self.assertIn(text, en)
        he = self.client.get("/safety/japan/?lang=he").content.decode()
        self.assertIn("שומרים על עצמנו ביפן", he)
        self.assertIn("קובאן", he)

    def test_uzbekistan_page_has_its_own_numbers(self):
        html = self.client.get("/safety/uzbekistan/").content.decode()
        for n in ("112", "101", "102", "103"):
            self.assertIn(f'href="tel:{n}"', html)
        self.assertNotIn("koban", html)
        self.assertEqual(self.client.get("/safety/mars/").status_code, 404)

    def test_family_page_follows_the_trip_and_is_linked(self):
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        from courses.builder import build_course
        from content_admin.models import Module
        from trips.models import Traveller, Trip

        call_command("load_content", "japan", "uzbekistan", verbosity=0)
        user = get_user_model().objects.create_user("safe@example.com", "safe@example.com")
        trip = Trip.objects.create(user=user, destination="uzbekistan")
        Traveller.objects.create(trip=trip, age=40)
        build_course(trip, list(Module.objects.filter(country="uzbekistan").values_list("id", flat=True)))
        self.client.force_login(user)
        self.assertContains(self.client.get("/safety/"), "Staying safe in Uzbekistan")
        course = self.client.get("/course/").content.decode()
        self.assertIn("Safety: the important things", course)
        self.assertGreaterEqual(course.count('href="/safety/"'), 2)  # the header and the adventure page
