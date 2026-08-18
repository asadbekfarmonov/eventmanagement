import importlib
import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

# 1x1 transparent PNG
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6360000002000154a24f2b0000000049454e44ae426082"
)


class Batch2WebFeaturesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.admin_tg_id = 555001
        self.user_tg_id = 555002
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "bot.db")

        self._env_keys = (
            "DATABASE_PATH",
            "ADMIN_IDS",
            "BOT_TOKEN",
            "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL",
            "UPLOAD_DIR",
            "UPLOAD_MAX_MB",
            "ADMIN_WEB_PASSWORD",
            "EMAIL_LOGIN_DEV_MODE",
            "EMAIL_LOGIN_RATE_LIMIT",
            "BOOKING_RATE_LIMIT",
            "QUOTE_RATE_LIMIT",
            "RESEND_API_KEY",
            "RESEND_FROM_EMAIL",
            "LEGACY_WEB_REGISTER_ENABLED",
            "GOOGLE_CLIENT_ID",
        )
        self._env_backup = {key: os.environ.get(key) for key in self._env_keys}
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
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp_dir.cleanup()

    # ---- helpers -------------------------------------------------------

    def _make_event(self, early_qty=10):
        return self.db.create_event(
            title="Test Event",
            event_datetime="2026-03-03 16:00",
            location="Budapest",
            caption="Caption",
            photo_file_id="",
            early_boy_price=2500.0,
            early_girl_price=2500.0,
            early_qty=early_qty,
            tier1_boy_price=3500.0,
            tier1_girl_price=3500.0,
            tier1_qty=0,
            tier2_boy_price=4000.0,
            tier2_girl_price=4000.0,
            tier2_qty=0,
        )

    def _web_login(self, email, name="Web", surname="Guest", phone="+36 20 123 4567"):
        start = self.client.post(
            "/api/web/login/start",
            json={"name": name, "surname": surname, "email": email, "phone": phone},
        )
        self.assertEqual(start.status_code, 200, start.text)
        code = start.json()["dev_code"]
        verify = self.client.post(
            "/api/web/login/verify",
            json={"email": email, "code": code},
        )
        self.assertEqual(verify.status_code, 200, verify.text)
        return verify

    def _book_web(self, event_id=None, boys=1, girls=0, attendees=None):
        names = attendees or ["Web Guest"]
        return self.client.post(
            "/api/book_with_payment",
            data={
                "event_id": str(event_id or self.event_id),
                "boys": str(boys),
                "girls": str(girls),
                "attendees": json.dumps(names),
                "discounted_attendee_indexes": "[]",
                "terms_accepted": "true",
            },
            files=[("file", ("proof.png", PNG_BYTES, "image/png"))],
        )

    # ---- H1: web cancel ------------------------------------------------

    def test_web_cancel_pending_releases_stock(self):
        event_id = self._make_event(early_qty=1)
        self._web_login("cancel.stock@example.invalid")
        booking = self._book_web(event_id=event_id, boys=1, girls=0)
        self.assertEqual(booking.status_code, 200, booking.text)
        code = booking.json()["code"]

        # Stock is now exhausted for a second booking.
        sold_out = self.client.post(
            "/api/quote", json={"event_id": event_id, "boys": 1, "girls": 0}
        )
        self.assertEqual(sold_out.status_code, 409, sold_out.text)

        cancel = self.client.post("/api/web/cancel", json={"code": code})
        self.assertEqual(cancel.status_code, 200, cancel.text)
        self.assertTrue(cancel.json()["ok"])
        self.assertEqual(cancel.json()["status"], "cancelled")

        # Stock freed -> quote succeeds again.
        freed = self.client.post(
            "/api/quote", json={"event_id": event_id, "boys": 1, "girls": 0}
        )
        self.assertEqual(freed.status_code, 200, freed.text)

    def test_web_cancel_approved_returns_400(self):
        self._web_login("cancel.approved@example.invalid")
        booking = self._book_web(boys=1, girls=0)
        self.assertEqual(booking.status_code, 200, booking.text)
        code = booking.json()["code"]

        reservation = self.db.get_reservation_by_code(code)
        ok, _msg, _res = self.db.approve_reservation(reservation.id, self.admin_tg_id)
        self.assertTrue(ok)

        cancel = self.client.post("/api/web/cancel", json={"code": code})
        self.assertEqual(cancel.status_code, 400, cancel.text)
        self.assertIn("contact us", cancel.json()["detail"].lower())

    def test_web_cancel_other_users_code_returns_404(self):
        # User A books.
        self._web_login("owner.a@example.invalid")
        booking = self._book_web(boys=1, girls=0)
        self.assertEqual(booking.status_code, 200, booking.text)
        code = booking.json()["code"]

        # User B logs in (replaces cookie) and tries to cancel A's code.
        self.client.cookies.clear()
        self._web_login("intruder.b@example.invalid", name="Intr", surname="Uder")
        cancel = self.client.post("/api/web/cancel", json={"code": code})
        self.assertEqual(cancel.status_code, 404, cancel.text)

    # ---- H2: admin_note in my_tickets ---------------------------------

    def test_my_tickets_includes_admin_note_reflecting_rejection(self):
        self._web_login("rejected.note@example.invalid")
        booking = self._book_web(boys=1, girls=0)
        self.assertEqual(booking.status_code, 200, booking.text)
        code = booking.json()["code"]

        reservation = self.db.get_reservation_by_code(code)
        ok, _msg, _res = self.db.reject_reservation(
            reservation.id, self.admin_tg_id, "Payment proof unreadable"
        )
        self.assertTrue(ok)

        tickets = self.client.get("/api/my_tickets")
        self.assertEqual(tickets.status_code, 200, tickets.text)
        items = tickets.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertIn("admin_note", items[0])
        self.assertEqual(items[0]["admin_note"], "Payment proof unreadable")
        self.assertEqual(items[0]["status"], "rejected")

    # ---- M4: web logout ------------------------------------------------

    def test_web_logout_invalidates_session_and_clears_cookie(self):
        self._web_login("logout.user@example.invalid")
        me_ok = self.client.get("/api/me")
        self.assertEqual(me_ok.status_code, 200, me_ok.text)

        logout = self.client.post("/api/web/logout")
        self.assertEqual(logout.status_code, 200, logout.text)
        self.assertTrue(logout.json()["ok"])
        set_cookie = logout.headers.get("set-cookie", "")
        self.assertIn("bt_web_session=", set_cookie)

        # Cookie cleared client-side -> subsequent /api/me is unauthorized.
        me_after = self.client.get("/api/me")
        self.assertEqual(me_after.status_code, 401, me_after.text)

    def test_web_logout_session_row_deleted_server_side(self):
        verify = self._web_login("logout.server@example.invalid")
        # Grab the raw token from the set-cookie so we can re-use it after logout.
        token = self.client.cookies.get("bt_web_session")
        self.assertTrue(token)
        self.client.post("/api/web/logout")
        # The server-side session must be gone even if a stale cookie is re-presented.
        self.client.cookies.set("bt_web_session", token)
        me_stale = self.client.get("/api/me")
        self.assertEqual(me_stale.status_code, 401, me_stale.text)

    # ---- M3: server-side phone enforcement -----------------------------

    def test_web_booking_without_phone_returns_400(self):
        user, token = self.db.create_or_update_web_user_by_email(
            "No", "Phone", "nophone@example.invalid", ""
        )
        self.assertEqual((user.phone or "").strip(), "")
        self.client.cookies.set("bt_web_session", token)
        booking = self._book_web(boys=1, girls=0)
        self.assertEqual(booking.status_code, 400, booking.text)
        self.assertIn("phone number", booking.json()["detail"].lower())

    def test_web_booking_with_phone_succeeds(self):
        self._web_login("hasphone@example.invalid", phone="+36 30 555 1212")
        booking = self._book_web(boys=1, girls=0)
        self.assertEqual(booking.status_code, 200, booking.text)
        self.assertTrue(booking.json()["ok"])

    # ---- M5: login must not overwrite saved profile --------------------

    def test_email_login_does_not_overwrite_existing_profile(self):
        email = "keep.profile@example.invalid"
        self._web_login(email, name="Anna", surname="Kovacs", phone="+36 20 111 2222")

        # Second login with DIFFERENT typed values for the same email.
        self.client.cookies.clear()
        self._web_login(email, name="Zoltan", surname="Nagy", phone="+36 99 000 0000")

        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200, me.text)
        profile = me.json()["profile"]
        self.assertEqual(profile["name"], "Anna")
        self.assertEqual(profile["surname"], "Kovacs")
        self.assertEqual(profile["phone"], "+36 20 111 2222")
        self.assertEqual(profile["email"], email)

    def test_email_login_fills_empty_stored_fields(self):
        # Existing user created with an empty phone.
        user, _token = self.db.create_or_update_web_user_by_email(
            "Empty", "Phone", "fill.me@example.invalid", ""
        )
        self.assertEqual((user.phone or "").strip(), "")
        # A subsequent login providing a phone should fill the empty slot.
        self._web_login("fill.me@example.invalid", name="Empty", surname="Phone", phone="+36 70 123 4567")
        refreshed = self.db.get_user_by_email("fill.me@example.invalid")
        self.assertEqual(refreshed.phone, "+36 70 123 4567")

    def test_email_login_creates_and_logs_in_new_user(self):
        verify = self._web_login("brand.new@example.invalid", name="Brand", surname="New")
        profile = verify.json()["profile"]
        self.assertEqual(profile["email"], "brand.new@example.invalid")
        self.assertEqual(profile["source"], "website")
        self.assertLess(int(profile["tg_id"]), 0)
        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200, me.text)

    def test_google_login_creates_and_logs_in_new_user(self):
        # Bypass the network token verification with a stub payload.
        self.server._verify_google_credential = lambda credential: {
            "email": "google.user@example.invalid",
            "given_name": "Goo",
            "family_name": "Gle",
        }
        resp = self.client.post(
            "/api/web/login/google",
            json={"credential": "x" * 40, "phone": "+36 20 000 1111"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        profile = resp.json()["profile"]
        self.assertEqual(profile["email"], "google.user@example.invalid")
        self.assertEqual(profile["source"], "website")
        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["profile"]["email"], "google.user@example.invalid")


if __name__ == "__main__":
    unittest.main()
