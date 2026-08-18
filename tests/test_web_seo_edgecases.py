import importlib
import os
import tempfile
import unittest
from xml.etree import ElementTree

from fastapi.testclient import TestClient


class _BaseSeoEnv(unittest.TestCase):
    WEB_APP_URL = ""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "seo_edge.db")
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
        os.environ["WEB_APP_URL"] = self.WEB_APP_URL
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


class WebSeoEmptyWebAppUrlTests(_BaseSeoEnv):
    """WEB_APP_URL unset: robots/sitemap must fall back to relative paths."""

    WEB_APP_URL = ""

    def test_robots_txt_relative_sitemap_fallback(self):
        resp = self.client.get("/robots.txt")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("Sitemap: /sitemap.xml", resp.text)
        # No stray absolute URL when WEB_APP_URL empty
        self.assertNotIn("Sitemap: /sitemap.xml/", resp.text)
        self.assertIn("Disallow: /api/", resp.text)
        self.assertIn("Disallow: /uploads/", resp.text)
        self.assertIn("Disallow: /checkin/", resp.text)

    def test_sitemap_xml_relative_home_and_wellformed(self):
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("xml", resp.headers["content-type"])
        root = ElementTree.fromstring(resp.text)
        self.assertTrue(root.tag.endswith("urlset"))
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [e.text for e in root.findall(".//sm:loc", ns)]
        self.assertEqual(locs, ["/"])


class WebSeoRouteIntegrityTests(_BaseSeoEnv):
    """404 handler must NOT hijack legitimate 200 routes or redirects."""

    WEB_APP_URL = "https://budapesttunderi.com"

    def test_legit_routes_not_hijacked(self):
        for path, ctype in (
            ("/", "text/html"),
            ("/health", "application/json"),
            ("/robots.txt", "text/plain"),
            ("/sitemap.xml", "xml"),
        ):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, f"{path}: {resp.status_code}")
            self.assertIn(ctype, resp.headers["content-type"], path)

    def test_checkin_redirect_not_hijacked(self):
        resp = self.client.get("/checkin/sometoken", follow_redirects=False)
        self.assertEqual(resp.status_code, 307, resp.text)
        self.assertIn("open_admin=1", resp.headers["location"])
        self.assertIn("checkin=sometoken", resp.headers["location"])

    def test_unknown_uploads_path_missing_query_not_html(self):
        # /uploads without signed query -> validation error (422), never branded HTML 404
        resp = self.client.get("/uploads/nope.jpg")
        self.assertIn(resp.status_code, {403, 422})
        self.assertNotIn("Return to Budapest Tunderi", resp.text)


if __name__ == "__main__":
    unittest.main()
