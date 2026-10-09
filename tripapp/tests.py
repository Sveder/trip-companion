from django.test import TestCase


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
        self.assertContains(r, "age group")
        self.assertContains(r, "how many days")
        self.assertNotContains(r, "Videos")
        self.assertContains(r, 'href="mailto:m@sveder.com?subject=Delete%20my%20Trip%20Companion%20account"')
        he = self.client.get("/privacy/?lang=he").content.decode()
        for text in ("תמונות שאתם מצלמים ביפן", "קבוצת גיל", "לכמה ימים", "מחיקת החשבון"):
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
        # T105: under 600 px the badge is 80 px and absolute, so the phone header pads only 70 px.
        import re
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static/css/app.css").read_text()
        phone = css[css.index("T105: the header is ONE line"):]
        self.assertRegex(phone, r"html \.sv2 \{ position: absolute; --sv: 80px !important; \}")
        right = int(re.search(r"\.top \{[^}]*padding: \S+ (\d+)px", phone).group(1))
        self.assertGreaterEqual(right, 70 - 1)


class HeaderMenuTests(TestCase):
    """T105: a signed-in phone header folds the links behind one Menu button."""

    def test_signed_in_header_has_the_menu_button_and_the_links(self):
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user("m@example.com", "m@example.com", "pw-123456")
        self.client.force_login(u)
        html = self.client.get("/", follow=True).content.decode()
        self.assertIn('class="menu-btn link" aria-expanded="false" aria-controls="top-menu"', html)
        self.assertIn('class="top-menu foldable" id="top-menu"', html)
        self.assertIn("Our course", html)
        self.client.cookies.load({"django_language": "he"})
        self.assertIn("תפריט", self.client.get("/", follow=True).content.decode())

    def test_signed_out_header_has_no_menu_button(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("menu-btn", html)
        self.assertIn('class="top-menu" id="top-menu"', html)
        self.assertIn("lang-switch", html)


class OldTvBrowserTests(TestCase):
    """The LG TV runs Chrome 87: no CSS aspect-ratio, no :has(), no Array.prototype.at (T101)."""

    def css(self):
        from pathlib import Path
        return (Path(__file__).resolve().parent.parent / "static/css/app.css").read_text()

    def test_pages_load_the_compat_script_and_the_at_polyfill(self):
        html = self.client.get("/").content.decode()
        self.assertIn("js/compat.js", html)
        self.assertIn("C.prototype.at", html)

    def test_boxes_that_hold_absolute_children_do_not_need_aspect_ratio(self):
        css = self.css()
        for sel in (".plane", ".video-frame"):
            self.assertIn(sel + '::before { content: ""; display: block; padding-top:', css)
            rule = css.split("\n" + sel + " {", 1)[1].split("}", 1)[0]
            self.assertNotIn("aspect-ratio", rule)

    def test_every_has_checked_rule_has_a_class_twin(self):
        css = self.css()
        self.assertIn(".pick.on", css)
        for twin in (".module.on {", ".module.on .switch {", ".module.on .switch::after {", '[dir="rtl"] .module.on .switch::after'):
            self.assertIn(twin, css)
