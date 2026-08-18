import importlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

# Minimal valid 1x1 PNG (magic bytes + IEND).
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02"
    b"\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f\x00\x02\xeb"
    b"\x01\xf6\xc5\xbb\xc7\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 32


class CarouselDbTests(unittest.TestCase):
    def setUp(self):
        import ticketbot.database as database

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = database.Database(os.path.join(self.temp_dir.name, "db.db"))
        self.addCleanup(self.db.conn.close)

    def test_fresh_schema_has_carousel_table(self):
        cols = self.db._table_columns("carousel_images")
        self.assertEqual(cols, {"id", "image_url", "position", "created_at"})

    def test_add_list_delete_roundtrip(self):
        self.assertEqual(self.db.list_carousel_images(), [])
        row1 = self.db.add_carousel_image("/event-media/a.png")
        row2 = self.db.add_carousel_image("/event-media/b.jpg")
        self.assertEqual(row1["image_url"], "/event-media/a.png")
        self.assertEqual(row1["position"], 1)
        self.assertEqual(row2["position"], 2)

        rows = self.db.list_carousel_images()
        self.assertEqual([r["image_url"] for r in rows], ["/event-media/a.png", "/event-media/b.jpg"])

        removed = self.db.delete_carousel_image(row1["id"])
        self.assertEqual(removed, "/event-media/a.png")
        rows = self.db.list_carousel_images()
        self.assertEqual([r["image_url"] for r in rows], ["/event-media/b.jpg"])

        self.assertIsNone(self.db.delete_carousel_image(999999))


class CarouselMigrationTests(unittest.TestCase):
    def test_migration_adds_carousel_table_to_legacy_db(self):
        import sqlite3

        import ticketbot.database as database

        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = os.path.join(temp_dir.name, "legacy.db")

        # Legacy DB with just a users table, no carousel_images.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, "
            "name TEXT, surname TEXT, phone TEXT)"
        )
        conn.commit()
        conn.close()

        db = database.Database(db_path)
        try:
            cols = db._table_columns("carousel_images")
            self.assertIn("image_url", cols)
            self.assertIn("position", cols)
        finally:
            db.conn.close()


class CarouselApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.admin_tg_id = 7164876915
        self.user_tg_id = 511308234
        self._env_keys = (
            "DATABASE_PATH",
            "ADMIN_IDS",
            "BOT_TOKEN",
            "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL",
            "UPLOAD_DIR",
            "EVENT_MEDIA_DIR",
            "UPLOAD_MAX_MB",
            "ADMIN_WEB_PASSWORD",
            "EMAIL_LOGIN_DEV_MODE",
        )
        self._env_backup = {k: os.environ.get(k) for k in self._env_keys}
        os.environ["DATABASE_PATH"] = os.path.join(self.temp_dir.name, "test.db")
        os.environ["ADMIN_IDS"] = str(self.admin_tg_id)
        os.environ["BOT_TOKEN"] = ""
        os.environ["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "1"
        os.environ["WEB_APP_URL"] = "https://example.invalid"
        os.environ["UPLOAD_DIR"] = os.path.join(self.temp_dir.name, "uploads")
        os.environ["EVENT_MEDIA_DIR"] = os.path.join(self.temp_dir.name, "event_media")
        os.environ["UPLOAD_MAX_MB"] = "5"
        os.environ["ADMIN_WEB_PASSWORD"] = "test-admin-password"
        os.environ["EMAIL_LOGIN_DEV_MODE"] = "1"

        import ticketbot.miniapp_server as miniapp_server

        self.server = importlib.reload(miniapp_server)
        self.client = TestClient(self.server.app)
        self.addCleanup(self.client.close)
        self.db = self.server.db
        self.media_dir = Path(os.environ["EVENT_MEDIA_DIR"])

    def tearDown(self):
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _upload(self, content=PNG_BYTES, mime="image/png", name="carousel.png", tg_id=None):
        return self.client.post(
            "/api/admin/carousel",
            data={"tg_id": str(self.admin_tg_id if tg_id is None else tg_id)},
            files=[("file", (name, content, mime))],
        )

    def test_public_carousel_empty_then_populated_with_absolute_urls(self):
        resp = self.client.get("/api/carousel")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json(), {"items": []})

        up = self._upload()
        self.assertEqual(up.status_code, 200, up.text)
        item = up.json()["item"]
        self.assertTrue(item["url"].startswith("https://example.invalid/event-media/"), item["url"])

        resp = self.client.get("/api/carousel")
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], item["id"])
        self.assertTrue(items[0]["url"].startswith("https://example.invalid/event-media/"), items[0]["url"])

    def test_upload_requires_admin(self):
        resp = self._upload(tg_id=self.user_tg_id)
        self.assertIn(resp.status_code, (401, 403), resp.text)
        # No file should be stored.
        self.assertEqual(list(self.media_dir.glob("*")), [])
        self.assertEqual(self.db.list_carousel_images(), [])

    def test_upload_rejects_non_image(self):
        resp = self._upload(content=b"not an image", mime="text/plain", name="x.txt")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(self.db.list_carousel_images(), [])

    def test_upload_rejects_mismatched_content(self):
        resp = self._upload(content=b"plain text bytes", mime="image/png", name="x.png")
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_upload_accepts_jpeg(self):
        resp = self._upload(content=JPEG_BYTES, mime="image/jpeg", name="c.jpg")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["item"]["url"].endswith(".jpg"))

    def test_upload_rejects_oversize(self):
        # Content-type passes the initial check but the body exceeds MAX_UPLOAD_BYTES,
        # so the server must reject with 413 before storing anything.
        oversize = PNG_BYTES + b"\x00" * (self.server.MAX_UPLOAD_BYTES + 1)
        resp = self._upload(content=oversize, mime="image/png", name="big.png")
        self.assertEqual(resp.status_code, 413, resp.text)
        self.assertEqual(list(self.media_dir.glob("*")), [])
        self.assertEqual(self.db.list_carousel_images(), [])

    def test_upload_rejects_empty_body(self):
        resp = self._upload(content=b"", mime="image/png", name="empty.png")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(self.db.list_carousel_images(), [])

    def test_uploaded_image_is_served_by_event_media(self):
        up = self._upload()
        self.assertEqual(up.status_code, 200, up.text)
        url = up.json()["item"]["url"]
        path = "/event-media/" + Path(url).name
        media_resp = self.client.get(path)
        self.assertEqual(media_resp.status_code, 200, media_resp.text)
        self.assertEqual(media_resp.headers["content-type"], "image/png")
        self.assertEqual(media_resp.content, PNG_BYTES)

    def test_delete_removes_row_and_file(self):
        up = self._upload()
        self.assertEqual(up.status_code, 200, up.text)
        image_id = up.json()["item"]["id"]
        stored_name = Path(up.json()["item"]["url"]).name
        self.assertTrue((self.media_dir / stored_name).is_file())

        resp = self.client.post(
            "/api/admin/carousel/delete",
            json={"tg_id": self.admin_tg_id, "id": image_id},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json(), {"ok": True})
        self.assertEqual(self.db.list_carousel_images(), [])
        self.assertFalse((self.media_dir / stored_name).is_file())

    def test_delete_requires_admin(self):
        up = self._upload()
        image_id = up.json()["item"]["id"]
        resp = self.client.post(
            "/api/admin/carousel/delete",
            json={"tg_id": self.user_tg_id, "id": image_id},
        )
        self.assertIn(resp.status_code, (401, 403), resp.text)
        # Row must remain.
        self.assertEqual(len(self.db.list_carousel_images()), 1)


if __name__ == "__main__":
    unittest.main()
