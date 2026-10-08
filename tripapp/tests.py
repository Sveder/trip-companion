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
