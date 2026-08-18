import importlib
import os
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

from fastapi.testclient import TestClient


class WebSeoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "seo_test.db")
        self._env_keys = (
            "DATABASE_PATH",
            "ADMIN_IDS",
            "BOT_TOKEN",
            "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL",
            "UPLOAD_DIR",
        )
        self._env_backup = {key: os.environ.get(key) for key in self._env_keys}
        os.environ["DATABASE_PATH"] = self.db_path
        os.environ["ADMIN_IDS"] = ""
        os.environ["BOT_TOKEN"] = ""
        os.environ["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "1"
        os.environ["WEB_APP_URL"] = "https://budapesttunderi.com"
        os.environ["UPLOAD_DIR"] = os.path.join(self.temp_dir.name, "uploads")

        import ticketbot.miniapp_server as miniapp_server

        self.server = importlib.reload(miniapp_server)
        self.client = TestClient(self.server.app)

    def tearDown(self) -> None:
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp_dir.cleanup()

    def test_robots_txt(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        body = response.text
        self.assertIn("User-agent: *", body)
        self.assertIn("Disallow: /api/", body)
        self.assertIn("Sitemap", body)
        self.assertIn("https://budapesttunderi.com/sitemap.xml", body)

    def test_sitemap_xml(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("xml", response.headers["content-type"])
        self.assertIn("<urlset", response.text)
        root = ElementTree.fromstring(response.text)
        self.assertTrue(root.tag.endswith("urlset"))
        self.assertIn("https://budapesttunderi.com/", response.text)

    def test_unknown_non_api_path_returns_html_404(self):
        response = self.client.get("/definitely-not-a-real-page")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.headers["content-type"].startswith("text/html"))
        self.assertIn("404", response.text)

    def test_unknown_api_path_returns_json_404(self):
        response = self.client.get("/api/definitely-not-a-real-endpoint")
        self.assertEqual(response.status_code, 404)
        self.assertIn("application/json", response.headers["content-type"])
        self.assertIn("detail", response.json())

    def test_index_html_has_og_title_and_canonical(self):
        index_path = Path(self.server.WEB_DIR) / "index.html"
        html = index_path.read_text(encoding="utf-8")
        self.assertIn('property="og:title"', html)
        self.assertIn('rel="canonical"', html)

    def test_csp_allows_google_identity_services(self):
        # Google Identity Services (button + FedCM credential flow) makes runtime
        # requests to accounts.google.com; connect-src/style-src must allow it or
        # sign-in fails for some browsers.
        resp = self.client.get("/")
        csp = resp.headers.get("content-security-policy", "")
        self.assertIn("connect-src 'self' https://accounts.google.com", csp)
        self.assertIn("script-src", csp)
        self.assertIn("https://accounts.google.com", csp.split("style-src", 1)[1].split(";", 1)[0])


if __name__ == "__main__":
    unittest.main()
