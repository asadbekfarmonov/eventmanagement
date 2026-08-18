"""Adversarial QA gap tests for Batch 2 (web-user completeness).

These complement tests/test_batch2_web_features.py by exercising paths the
implementer's tests bypassed:
  * approve/reject through the real HTTP endpoints (which invoke _send_email),
    not the db.* helpers directly;
  * _send_email best-effort safety when "configured" but the network fails;
  * logout Set-Cookie max-age=0;
  * web/cancel unknown-code -> 404;
  * Telegram user (positive tg_id) is unaffected by the web phone rule.
"""

import importlib
import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6360000002000154a24f2b0000000049454e44ae426082"
)


class Batch2QaGapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.admin_tg_id = 555901
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "bot.db")
        self._env_keys = (
            "DATABASE_PATH", "ADMIN_IDS", "BOT_TOKEN", "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL", "UPLOAD_DIR", "UPLOAD_MAX_MB", "ADMIN_WEB_PASSWORD",
            "EMAIL_LOGIN_DEV_MODE", "EMAIL_LOGIN_RATE_LIMIT", "BOOKING_RATE_LIMIT",
            "QUOTE_RATE_LIMIT", "RESEND_API_KEY", "RESEND_FROM_EMAIL",
            "LEGACY_WEB_REGISTER_ENABLED", "GOOGLE_CLIENT_ID",
        )
        self._env_backup = {k: os.environ.get(k) for k in self._env_keys}
        os.environ["DATABASE_PATH"] = self.db_path
        os.environ["ADMIN_IDS"] = str(self.admin_tg_id)
        os.environ["BOT_TOKEN"] = ""
        os.environ["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "1"
        os.environ["WEB_APP_URL"] = "https://example.invalid"
        os.environ["UPLOAD_DIR"] = os.path.join(self.temp_dir.name, "uploads")
        os.environ["UPLOAD_MAX_MB"] = "5"
        os.environ["ADMIN_WEB_PASSWORD"] = "test-admin-password"
        os.environ["EMAIL_LOGIN_DEV_MODE"] = "1"
        os.environ["EMAIL_LOGIN_RATE_LIMIT"] = "50"
        os.environ["BOOKING_RATE_LIMIT"] = "50"
        os.environ["QUOTE_RATE_LIMIT"] = "200"
        os.environ["RESEND_API_KEY"] = ""
        os.environ["RESEND_FROM_EMAIL"] = ""
        os.environ["LEGACY_WEB_REGISTER_ENABLED"] = "0"
        os.environ["GOOGLE_CLIENT_ID"] = ""

        import ticketbot.miniapp_server as miniapp_server
        self.server = importlib.reload(miniapp_server)
        self.client = TestClient(self.server.app)
        self.db = self.server.db
        self.event_id = self._make_event(early_qty=10)

    def tearDown(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.temp_dir.cleanup()

    # ---- helpers -------------------------------------------------------
    def _make_event(self, early_qty=10):
        return self.db.create_event(
            title="Gap Event", event_datetime="2026-04-04 20:00", location="Budapest",
            caption="Cap", photo_file_id="", early_boy_price=2500.0, early_girl_price=2500.0,
            early_qty=early_qty, tier1_boy_price=3500.0, tier1_girl_price=3500.0, tier1_qty=0,
            tier2_boy_price=4000.0, tier2_girl_price=4000.0, tier2_qty=0,
        )

    def _web_login(self, email, name="Web", surname="Guest", phone="+36 20 123 4567"):
        start = self.client.post("/api/web/login/start",
            json={"name": name, "surname": surname, "email": email, "phone": phone})
        self.assertEqual(start.status_code, 200, start.text)
        code = start.json()["dev_code"]
        verify = self.client.post("/api/web/login/verify", json={"email": email, "code": code})
        self.assertEqual(verify.status_code, 200, verify.text)
        return verify

    def _book_web(self, event_id=None, boys=1, girls=0, attendees=None, tg_id=None):
        data = {
            "event_id": str(event_id or self.event_id), "boys": str(boys), "girls": str(girls),
            "attendees": json.dumps(attendees or ["Web Guest"]),
            "discounted_attendee_indexes": "[]", "terms_accepted": "true",
        }
        if tg_id is not None:
            data["tg_id"] = str(tg_id)
        return self.client.post("/api/book_with_payment", data=data,
            files=[("file", ("proof.png", PNG_BYTES, "image/png"))])

    # ---- GAP 1: approve via the REAL endpoint (exercises _send_email) --
    def test_approve_via_api_endpoint_is_safe_and_confirms(self):
        self._web_login("api.approve@example.invalid")
        booking = self._book_web(boys=1, girls=0)
        self.assertEqual(booking.status_code, 200, booking.text)
        code = booking.json()["code"]
        res = self.db.get_reservation_by_code(code)

        # Web-buyer HAS an email + Resend UNCONFIGURED -> endpoint must not raise.
        self.client.cookies.clear()
        approve = self.client.post("/api/admin/reservation/approve",
            json={"reservation_id": res.id, "tg_id": self.admin_tg_id})
        self.assertEqual(approve.status_code, 200, approve.text)
        self.assertTrue(approve.json()["ok"])

        # my_tickets (as the buyer) now shows approved with QR passes.
        self._web_login("api.approve@example.invalid")
        tickets = self.client.get("/api/my_tickets")
        self.assertEqual(tickets.status_code, 200, tickets.text)
        item = tickets.json()["items"][0]
        self.assertEqual(item["status"], "approved")
        self.assertTrue(item["tickets"][0].get("qr_url"))

    def test_reject_via_api_endpoint_is_safe_and_surfaces_note(self):
        self._web_login("api.reject@example.invalid")
        booking = self._book_web(boys=1, girls=0)
        self.assertEqual(booking.status_code, 200, booking.text)
        code = booking.json()["code"]
        res = self.db.get_reservation_by_code(code)

        self.client.cookies.clear()
        reject = self.client.post("/api/admin/reservation/reject",
            json={"reservation_id": res.id, "tg_id": self.admin_tg_id,
                  "note": "Blurry payment screenshot"})
        self.assertEqual(reject.status_code, 200, reject.text)
        self.assertTrue(reject.json()["ok"])

        self._web_login("api.reject@example.invalid")
        tickets = self.client.get("/api/my_tickets")
        item = tickets.json()["items"][0]
        self.assertEqual(item["status"], "rejected")
        self.assertEqual(item["admin_note"], "Blurry payment screenshot")

    def test_reject_via_api_endpoint_requires_note(self):
        self._web_login("api.reject.empty@example.invalid")
        code = self._book_web(boys=1, girls=0).json()["code"]
        res = self.db.get_reservation_by_code(code)
        self.client.cookies.clear()
        reject = self.client.post("/api/admin/reservation/reject",
            json={"reservation_id": res.id, "tg_id": self.admin_tg_id, "note": "   "})
        self.assertEqual(reject.status_code, 400, reject.text)

    # ---- GAP 2: _send_email best-effort even when network fails --------
    def test_send_email_swallows_errors_when_configured(self):
        # Force the "configured, not dev" branch so it actually hits urlopen,
        # then guarantee the network call fails. It MUST NOT raise.
        self.server.EMAIL_LOGIN_DEV_MODE = False
        self.server.RESEND_API_KEY = "re_test_key"
        self.server.RESEND_FROM_EMAIL = "noreply@example.invalid"

        import urllib.request
        original = urllib.request.urlopen

        def boom(*_a, **_k):
            raise OSError("network down")

        urllib.request.urlopen = boom
        try:
            # Should return None without raising.
            self.assertIsNone(
                self.server._send_email("buyer@example.invalid", "s", "body")
            )
        finally:
            urllib.request.urlopen = original

    def test_send_email_noop_on_empty_recipient(self):
        self.assertIsNone(self.server._send_email("", "s", "b"))
        self.assertIsNone(self.server._send_email("   ", "s", "b"))

    # ---- GAP 3: logout Set-Cookie max-age=0 ----------------------------
    def test_logout_setcookie_has_max_age_zero(self):
        self._web_login("logout.maxage@example.invalid")
        logout = self.client.post("/api/web/logout")
        self.assertEqual(logout.status_code, 200, logout.text)
        set_cookie = logout.headers.get("set-cookie", "").lower()
        self.assertIn("bt_web_session=", set_cookie)
        self.assertIn("max-age=0", set_cookie)

    # ---- GAP 4: web/cancel unknown code -> 404 -------------------------
    def test_web_cancel_unknown_code_returns_404(self):
        self._web_login("cancel.unknown@example.invalid")
        cancel = self.client.post("/api/web/cancel", json={"code": "NOPE-DOES-NOT-EXIST"})
        self.assertEqual(cancel.status_code, 404, cancel.text)

    def test_web_cancel_requires_auth(self):
        # No session cookie at all -> unauthorized, not a 404/500.
        self.client.cookies.clear()
        cancel = self.client.post("/api/web/cancel", json={"code": "WHATEVER"})
        self.assertEqual(cancel.status_code, 401, cancel.text)

    # ---- GAP 5: Telegram user unaffected by web phone rule -------------
    def test_telegram_user_without_phone_can_book(self):
        tg_id = 424242  # positive => telegram user
        self.db.upsert_user(tg_id, "Tele", "Gram", "")
        stored = self.db.get_user(tg_id)
        self.assertEqual((stored.phone or "").strip(), "")
        self.client.cookies.clear()
        booking = self._book_web(boys=1, girls=0, attendees=["Tele Gram"], tg_id=tg_id)
        self.assertEqual(booking.status_code, 200, booking.text)
        self.assertTrue(booking.json()["ok"])


if __name__ == "__main__":
    unittest.main()
