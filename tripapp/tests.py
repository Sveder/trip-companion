from django.test import TestCase


class TvModeTests(TestCase):
    def test_off_by_default(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn('class="tv"', html)
        self.assertIn("js/tv.js", html)

    def test_query_turns_it_on_and_the_session_keeps_it(self):
        self.assertIn('<html lang="en" class="tv">', self.client.get("/?tv=1").content.decode())
        self.assertIn('class="tv"', self.client.get("/").content.decode())
        self.assertNotIn('class="tv"', self.client.get("/?tv=0").content.decode())
        self.assertNotIn('class="tv"', self.client.get("/").content.decode())

    def test_lg_webos_browser_gets_tv_mode(self):
        ua = "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0 Safari/537.36 WebAppManager"
        self.assertIn('class="tv"', self.client.get("/", HTTP_USER_AGENT=ua).content.decode())

    def test_phone_browser_does_not(self):
        ua = "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"
        self.assertNotIn('class="tv"', self.client.get("/", HTTP_USER_AGENT=ua).content.decode())
