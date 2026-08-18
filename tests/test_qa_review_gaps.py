"""QA review gap tests for admin-side fixes A/B/C.

Adversarial coverage added during test review:
- FIX A: pending + reject endpoints must require admin (no-session => 401).
- FIX B: web create path persists provided datetime/location (not the
  Budapest/now+7d default); create/update reject invalid datetime; update
  without a datetime key preserves the stored value.
- FIX C: logout clears the admin session cookie (Set-Cookie) and the same
  client becomes unauthorized.
"""

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


class QaReviewGapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.admin_tg_id = 7164876915
        self._keys = (
            "DATABASE_PATH", "ADMIN_IDS", "BOT_TOKEN", "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL", "UPLOAD_DIR", "UPLOAD_MAX_MB", "UPLOAD_RETENTION_DAYS",
            "UPLOAD_CLEANUP_INTERVAL_SECONDS", "UPLOAD_LINK_TTL_SECONDS",
            "RATE_LIMIT_WINDOW_SECONDS", "QUOTE_RATE_LIMIT", "BOOKING_RATE_LIMIT",
            "ADMIN_WEB_PASSWORD", "EMAIL_LOGIN_DEV_MODE", "EMAIL_LOGIN_TTL_SECONDS",
            "EMAIL_LOGIN_RATE_LIMIT", "EMAIL_CODE_ATTEMPT_LIMIT", "RESEND_API_KEY",
            "RESEND_FROM_EMAIL", "LEGACY_WEB_REGISTER_ENABLED",
            "SESSION_COOKIE_MAX_AGE_SECONDS", "GOOGLE_CLIENT_ID",
        )
        self._backup = {k: os.environ.get(k) for k in self._keys}
        os.environ.update({
            "DATABASE_PATH": os.path.join(self.temp_dir.name, "gaps.db"),
            "ADMIN_IDS": str(self.admin_tg_id),
            "BOT_TOKEN": "",
            "MINIAPP_ALLOW_TG_ID_FALLBACK": "1",
            "WEB_APP_URL": "https://example.invalid",
            "UPLOAD_DIR": os.path.join(self.temp_dir.name, "uploads"),
            "UPLOAD_MAX_MB": "5",
            "UPLOAD_RETENTION_DAYS": "7",
            "UPLOAD_CLEANUP_INTERVAL_SECONDS": "3600",
            "UPLOAD_LINK_TTL_SECONDS": "604800",
            "RATE_LIMIT_WINDOW_SECONDS": "60",
            "QUOTE_RATE_LIMIT": "120",
            "BOOKING_RATE_LIMIT": "12",
            "ADMIN_WEB_PASSWORD": "test-admin-password",
            "EMAIL_LOGIN_DEV_MODE": "1",
            "EMAIL_LOGIN_TTL_SECONDS": "600",
            "EMAIL_LOGIN_RATE_LIMIT": "20",
            "EMAIL_CODE_ATTEMPT_LIMIT": "5",
            "RESEND_API_KEY": "",
            "RESEND_FROM_EMAIL": "",
            "LEGACY_WEB_REGISTER_ENABLED": "0",
            "SESSION_COOKIE_MAX_AGE_SECONDS": "7776000",
            "GOOGLE_CLIENT_ID": "",
        })
        import ticketbot.miniapp_server as miniapp_server
        self.server = importlib.reload(miniapp_server)
        self.client = TestClient(self.server.app)
        self.db = self.server.db
        self.event_id = self.db.create_event(
            title="Seed Event", event_datetime="2026-03-03 16:00", location="Budapest",
            caption="", photo_file_id="", early_boy_price=1000.0, early_girl_price=1000.0,
            early_qty=10, tier1_boy_price=1500.0, tier1_girl_price=1500.0, tier1_qty=0,
            tier2_boy_price=2000.0, tier2_girl_price=2000.0, tier2_qty=0,
        )

    def tearDown(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass
        for k, v in self._backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.temp_dir.cleanup()

    def _login(self):
        resp = self.client.post("/api/admin/login", json={"password": "test-admin-password"})
        self.assertEqual(resp.status_code, 200, resp.text)

    def _create_body(self, **overrides):
        body = dict(
            title="Web Event", caption="", early_boy=1000, early_girl=1000, early_qty=5,
            tier1_boy=1500, tier1_girl=1500, tier1_qty=0, tier2_boy=2000, tier2_girl=2000,
            tier2_qty=0,
        )
        body.update(overrides)
        return body

    # ---- FIX A: auth required on all review endpoints ----
    def test_pending_requires_admin(self):
        resp = self.client.get("/api/admin/reservation/pending")
        self.assertIn(resp.status_code, (401, 403), resp.text)

    def test_reject_requires_admin(self):
        # Auth check must fire before note validation -> 401 even with a note.
        resp = self.client.post(
            "/api/admin/reservation/reject",
            json={"reservation_id": 1, "note": "some reason"},
        )
        self.assertIn(resp.status_code, (401, 403), resp.text)

    # ---- FIX B: create persists provided datetime/location, not default ----
    def test_create_simple_persists_provided_datetime_and_location(self):
        self._login()
        resp = self.client.post(
            "/api/admin/event/create_simple",
            json=self._create_body(event_datetime="2027-01-01 21:00", location="Akvarium Klub"),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        ev = resp.json()["event"]
        self.assertEqual(ev["event_datetime"], "2027-01-01 21:00")
        self.assertEqual(ev["location"], "Akvarium Klub")

    def test_create_simple_uses_defaults_when_datetime_location_omitted(self):
        self._login()
        resp = self.client.post("/api/admin/event/create_simple", json=self._create_body())
        self.assertEqual(resp.status_code, 200, resp.text)
        ev = resp.json()["event"]
        self.assertEqual(ev["location"], "Budapest")
        if ZoneInfo is not None:
            expected = (datetime.now(ZoneInfo("Europe/Budapest")) + timedelta(days=7)).date()
            got = datetime.strptime(ev["event_datetime"], "%Y-%m-%d %H:%M").date()
            self.assertEqual(got, expected)

    def test_create_simple_rejects_invalid_datetime(self):
        self._login()
        resp = self.client.post(
            "/api/admin/event/create_simple",
            json=self._create_body(event_datetime="01/01/2027 21:00"),
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("datetime", resp.json()["detail"].lower())

    # ---- FIX B: update persists via 'datetime' key, rejects bad, preserves when omitted ----
    def test_update_persists_datetime_and_location(self):
        self._login()
        resp = self.client.post(
            "/api/admin/event/update",
            json={"event_id": self.event_id, "updates": {"datetime": "2027-02-02 22:00", "location": "Racskert"}},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        ev = self.db.get_event(self.event_id)
        self.assertEqual(ev.event_datetime, "2027-02-02 22:00")
        self.assertEqual(ev.location, "Racskert")

    def test_update_rejects_invalid_datetime(self):
        self._login()
        resp = self.client.post(
            "/api/admin/event/update",
            json={"event_id": self.event_id, "updates": {"datetime": "not-a-date"}},
        )
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_update_without_datetime_key_preserves_value(self):
        self._login()
        before = self.db.get_event(self.event_id).event_datetime
        resp = self.client.post(
            "/api/admin/event/update",
            json={"event_id": self.event_id, "updates": {"caption": "changed only"}},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        after = self.db.get_event(self.event_id)
        self.assertEqual(after.event_datetime, before)
        self.assertEqual(after.caption, "changed only")

    def test_update_rejects_event_datetime_key(self):
        # Guard: the update payload must never rely on 'event_datetime'; that key
        # is unsupported by set_event_fields (frontend sends 'datetime').
        self._login()
        resp = self.client.post(
            "/api/admin/event/update",
            json={"event_id": self.event_id, "updates": {"event_datetime": "2027-02-02 22:00"}},
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("event_datetime", resp.json()["detail"])

    # ---- FIX C: logout clears cookie and revokes access ----
    def test_logout_clears_cookie_and_revokes_access(self):
        self._login()
        self.assertEqual(self.client.get("/api/admin/events").status_code, 200)
        logout = self.client.post("/api/admin/logout")
        self.assertEqual(logout.status_code, 200, logout.text)
        set_cookie = logout.headers.get("set-cookie", "")
        self.assertIn(self.server.ADMIN_SESSION_COOKIE, set_cookie)
        self.assertTrue("Max-Age=0" in set_cookie or "max-age=0" in set_cookie.lower())
        self.assertEqual(self.client.get("/api/admin/events").status_code, 401)


if __name__ == "__main__":
    unittest.main()
