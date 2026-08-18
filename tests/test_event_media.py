import importlib
import os
import sqlite3
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
# Minimal JPEG (only the SOI/APP0 magic prefix matters for magic-byte detection).
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 32


class EventMediaMigrationTests(unittest.TestCase):
    def test_migration_adds_photo_and_maps_columns(self):
        import ticketbot.database as database

        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = os.path.join(temp_dir.name, "legacy.db")

        # Build a legacy events table WITHOUT photo_url / maps_url.
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_datetime TEXT NOT NULL,
                location TEXT NOT NULL,
                caption TEXT NOT NULL DEFAULT '',
                photo_file_id TEXT NOT NULL DEFAULT '',
                early_bird_price REAL NOT NULL DEFAULT 0,
                early_bird_qty INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()
        conn.close()

        db = database.Database(db_path)
        try:
            cols = db._table_columns("events")
            self.assertIn("photo_url", cols)
            self.assertIn("maps_url", cols)
        finally:
            db.conn.close()

    def test_fresh_schema_has_photo_and_maps_columns(self):
        import ticketbot.database as database

        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db = database.Database(os.path.join(temp_dir.name, "fresh.db"))
        try:
            cols = db._table_columns("events")
            self.assertIn("photo_url", cols)
            self.assertIn("maps_url", cols)
        finally:
            db.conn.close()


class EventMediaDbTests(unittest.TestCase):
    def setUp(self):
        import ticketbot.database as database

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = database.Database(os.path.join(self.temp_dir.name, "db.db"))
        self.addCleanup(self.db.conn.close)

    def _create(self, **kwargs):
        params = dict(
            title="Ev",
            event_datetime="2026-03-03 16:00",
            location="Budapest",
            caption="",
            photo_file_id="",
            early_boy_price=1000.0,
            early_girl_price=1000.0,
            early_qty=10,
            tier1_boy_price=0.0,
            tier1_girl_price=0.0,
            tier1_qty=0,
            tier2_boy_price=0.0,
            tier2_girl_price=0.0,
            tier2_qty=0,
        )
        params.update(kwargs)
        return self.db.create_event(**params)

    def test_create_event_persists_maps_url(self):
        eid = self._create(maps_url="https://maps.google.com/?q=Budapest")
        event = self.db.get_event(eid)
        self.assertEqual(event.maps_url, "https://maps.google.com/?q=Budapest")
        self.assertEqual(event.photo_url, "")

    def test_set_event_fields_accepts_https_maps_url(self):
        eid = self._create()
        ok, msg = self.db.set_event_fields(eid, {"maps_url": "https://maps.google.com/x"})
        self.assertTrue(ok, msg)
        self.assertEqual(self.db.get_event(eid).maps_url, "https://maps.google.com/x")

    def test_set_event_fields_rejects_non_https_maps_url(self):
        eid = self._create()
        ok, msg = self.db.set_event_fields(eid, {"maps_url": "http://maps.google.com/x"})
        self.assertFalse(ok)
        self.assertIn("https://", msg)

    def test_set_event_fields_extracts_iframe_embed_src(self):
        eid = self._create()
        iframe = '<iframe src="https://www.google.com/maps/embed?pb=ABC" width="400"></iframe>'
        ok, msg = self.db.set_event_fields(eid, {"maps_url": iframe})
        self.assertTrue(ok, msg)
        self.assertEqual(self.db.get_event(eid).maps_url, "https://www.google.com/maps/embed?pb=ABC")

    def test_set_event_fields_allows_empty_maps_url(self):
        eid = self._create(maps_url="https://maps.google.com/x")
        ok, msg = self.db.set_event_fields(eid, {"maps_url": ""})
        self.assertTrue(ok, msg)
        self.assertEqual(self.db.get_event(eid).maps_url, "")

    def test_set_event_photo_updates_only_photo_url(self):
        eid = self._create()
        ok, msg = self.db.set_event_photo(eid, "/event-media/abc.png")
        self.assertTrue(ok, msg)
        self.assertEqual(self.db.get_event(eid).photo_url, "/event-media/abc.png")

    def test_set_event_fields_rejects_photo_url_field(self):
        eid = self._create()
        ok, msg = self.db.set_event_fields(eid, {"photo_url": "/event-media/x.png"})
        self.assertFalse(ok)
        self.assertIn("Unsupported field", msg)


class EventMediaApiTests(unittest.TestCase):
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

        self.event_id = self.db.create_event(
            title="Test Event",
            event_datetime="2026-03-03 16:00",
            location="Budapest",
            caption="Caption",
            photo_file_id="",
            early_boy_price=2500.0,
            early_girl_price=2500.0,
            early_qty=10,
            tier1_boy_price=0.0,
            tier1_girl_price=0.0,
            tier1_qty=0,
            tier2_boy_price=0.0,
            tier2_girl_price=0.0,
            tier2_qty=0,
        )

    def tearDown(self):
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _upload(self, content=PNG_BYTES, mime="image/png", name="banner.png", tg_id=None):
        return self.client.post(
            "/api/admin/event/photo",
            data={"tg_id": str(self.admin_tg_id if tg_id is None else tg_id), "event_id": str(self.event_id)},
            files=[("file", (name, content, mime))],
        )

    def test_upload_requires_admin(self):
        resp = self._upload(tg_id=self.user_tg_id)
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_upload_rejects_non_image(self):
        resp = self._upload(content=b"not an image", mime="text/plain", name="x.txt")
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_upload_rejects_mismatched_content(self):
        # content_type says png but bytes are not a valid image
        resp = self._upload(content=b"plain text bytes", mime="image/png", name="x.png")
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_upload_rejects_oversize_banner(self):
        # UPLOAD_MAX_MB=5 -> anything above the limit must be rejected with 413,
        # exercising the size guard in admin_event_photo before it is stored.
        oversize = PNG_BYTES + b"\x00" * (5 * 1024 * 1024 + 1)
        resp = self._upload(content=oversize, mime="image/png", name="big.png")
        self.assertEqual(resp.status_code, 413, resp.text)
        # Nothing must be persisted or written to disk on rejection.
        self.assertEqual(self.db.get_event(self.event_id).photo_url, "")
        self.assertEqual(list(self.media_dir.glob("*")), [])

    def test_upload_rejects_empty_banner(self):
        resp = self._upload(content=b"", mime="image/png", name="empty.png")
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_upload_stores_and_sets_photo_url_and_serves_public(self):
        resp = self._upload()
        self.assertEqual(resp.status_code, 200, resp.text)
        event = resp.json()["event"]
        photo_url = event["photo_url"]
        self.assertTrue(photo_url.startswith("/event-media/"), photo_url)

        stored = self.db.get_event(self.event_id)
        self.assertEqual(stored.photo_url, photo_url)
        self.assertTrue((self.media_dir / Path(photo_url).name).is_file())

        media_resp = self.client.get(photo_url)
        self.assertEqual(media_resp.status_code, 200, media_resp.text)
        self.assertEqual(media_resp.headers["content-type"], "image/png")
        self.assertEqual(
            media_resp.headers["cache-control"], "public, max-age=31536000, immutable"
        )
        self.assertEqual(media_resp.content, PNG_BYTES)

    def test_upload_accepts_jpeg(self):
        resp = self._upload(content=JPEG_BYTES, mime="image/jpeg", name="banner.jpg")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["event"]["photo_url"].endswith(".jpg"))

    def test_replacing_banner_deletes_old_file(self):
        first = self._upload()
        self.assertEqual(first.status_code, 200, first.text)
        first_name = Path(self.db.get_event(self.event_id).photo_url).name
        self.assertTrue((self.media_dir / first_name).is_file())

        second = self._upload(content=JPEG_BYTES, mime="image/jpeg", name="new.jpg")
        self.assertEqual(second.status_code, 200, second.text)
        second_name = Path(self.db.get_event(self.event_id).photo_url).name

        self.assertNotEqual(first_name, second_name)
        self.assertFalse((self.media_dir / first_name).is_file())
        self.assertTrue((self.media_dir / second_name).is_file())

    def test_event_media_path_traversal_is_blocked(self):
        resp = self.client.get("/event-media/..%2F..%2Fetc%2Fpasswd")
        self.assertEqual(resp.status_code, 404)

    def test_missing_event_media_returns_404(self):
        resp = self.client.get("/event-media/does-not-exist.png")
        self.assertEqual(resp.status_code, 404)

    def test_create_simple_persists_maps_url(self):
        resp = self.client.post(
            "/api/admin/event/create_simple",
            json={
                "tg_id": self.admin_tg_id,
                "title": "Mapped Event",
                "early_boy": 1000,
                "early_girl": 1000,
                "early_qty": 5,
                "tier1_boy": 0,
                "tier1_girl": 0,
                "tier1_qty": 0,
                "tier2_boy": 0,
                "tier2_girl": 0,
                "tier2_qty": 0,
                "maps_url": "https://maps.google.com/?q=Budapest",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["event"]["maps_url"], "https://maps.google.com/?q=Budapest")

    def test_create_simple_rejects_non_https_maps_url(self):
        resp = self.client.post(
            "/api/admin/event/create_simple",
            json={
                "tg_id": self.admin_tg_id,
                "title": "Bad Map",
                "early_boy": 1000,
                "early_girl": 1000,
                "early_qty": 5,
                "tier1_boy": 0,
                "tier1_girl": 0,
                "tier1_qty": 0,
                "tier2_boy": 0,
                "tier2_girl": 0,
                "tier2_qty": 0,
                "maps_url": "http://maps.google.com/x",
            },
        )
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_create_simple_extracts_iframe_embed_src(self):
        iframe = '<iframe src="https://www.google.com/maps/embed?pb=XYZ" height="300"></iframe>'
        resp = self.client.post(
            "/api/admin/event/create_simple",
            json={
                "tg_id": self.admin_tg_id,
                "title": "Iframe Map",
                "early_boy": 1000,
                "early_girl": 1000,
                "early_qty": 5,
                "tier1_boy": 0,
                "tier1_girl": 0,
                "tier1_qty": 0,
                "tier2_boy": 0,
                "tier2_girl": 0,
                "tier2_qty": 0,
                "maps_url": iframe,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["event"]["maps_url"], "https://www.google.com/maps/embed?pb=XYZ")

    def test_event_payload_includes_absolute_photo_url_and_maps(self):
        self._upload()
        self.db.set_event_fields(self.event_id, {"maps_url": "https://maps.google.com/x"})
        resp = self.client.get("/api/events")
        self.assertEqual(resp.status_code, 200, resp.text)
        item = next(i for i in resp.json()["items"] if i["id"] == self.event_id)
        self.assertTrue(item["photo_url"].startswith("https://example.invalid/event-media/"), item["photo_url"])
        self.assertEqual(item["maps_url"], "https://maps.google.com/x")

    def test_admin_events_includes_photo_and_maps(self):
        self._upload()
        self.db.set_event_fields(self.event_id, {"maps_url": "https://maps.google.com/x"})
        resp = self.client.get("/api/admin/events", params={"tg_id": self.admin_tg_id})
        self.assertEqual(resp.status_code, 200, resp.text)
        item = next(i for i in resp.json()["items"] if i["id"] == self.event_id)
        self.assertTrue(item["photo_url"].startswith("https://example.invalid/event-media/"))
        self.assertEqual(item["maps_url"], "https://maps.google.com/x")

    def test_delete_event_removes_media_file(self):
        self._upload()
        photo_name = Path(self.db.get_event(self.event_id).photo_url).name
        self.assertTrue((self.media_dir / photo_name).is_file())

        resp = self.client.post(
            "/api/admin/event/delete",
            json={"tg_id": self.admin_tg_id, "event_id": self.event_id},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertFalse((self.media_dir / photo_name).is_file())


if __name__ == "__main__":
    unittest.main()
