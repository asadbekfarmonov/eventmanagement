import base64
import importlib
import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class BatchABackendTests(unittest.TestCase):
    """Backend coverage for the guard role, PDF invoice, and purchase history."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "batch_a_test.db")
        self.admin_tg_id = 7164876915
        self.user_tg_id = 511308234
        self.admin_password = "test-admin-password"
        self.guard_password = "test-guard-password"
        self._env_keys = (
            "DATABASE_PATH",
            "ADMIN_IDS",
            "BOT_TOKEN",
            "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL",
            "UPLOAD_DIR",
            "ADMIN_WEB_PASSWORD",
            "GUARD_WEB_PASSWORD",
            "EMAIL_LOGIN_DEV_MODE",
            "RESEND_API_KEY",
            "RESEND_FROM_EMAIL",
            "SESSION_COOKIE_MAX_AGE_SECONDS",
            "GOOGLE_CLIENT_ID",
        )
        self._env_backup = {key: os.environ.get(key) for key in self._env_keys}
        os.environ["DATABASE_PATH"] = self.db_path
        os.environ["ADMIN_IDS"] = str(self.admin_tg_id)
        os.environ["BOT_TOKEN"] = ""
        os.environ["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "1"
        os.environ["WEB_APP_URL"] = "https://example.invalid"
        os.environ["UPLOAD_DIR"] = os.path.join(self.temp_dir.name, "uploads")
        os.environ["ADMIN_WEB_PASSWORD"] = self.admin_password
        os.environ["GUARD_WEB_PASSWORD"] = self.guard_password
        os.environ["EMAIL_LOGIN_DEV_MODE"] = "1"
        os.environ["RESEND_API_KEY"] = ""
        os.environ["RESEND_FROM_EMAIL"] = ""
        os.environ["SESSION_COOKIE_MAX_AGE_SECONDS"] = "7776000"
        os.environ["GOOGLE_CLIENT_ID"] = ""

        import ticketbot.miniapp_server as miniapp_server

        self.server = importlib.reload(miniapp_server)
        self.client = TestClient(self.server.app)
        self.db = self.server.db

        self.db.upsert_user(self.user_tg_id, "Buyer", "User", "+36 20 111 2222")
        user = self.db.get_user(self.user_tg_id)
        self.user_id = user.id
        self.db.conn.execute(
            "UPDATE users SET email = ? WHERE id = ?",
            ("buyer.person@example.invalid", self.user_id),
        )
        self.db.conn.commit()
        self.event_id = self.db.create_event(
            title="Test Event",
            event_datetime="2026-03-03 16:00",
            location="Budapest",
            caption="Caption",
            photo_file_id="",
            early_boy_price=2500.0,
            early_girl_price=2000.0,
            early_qty=10,
            tier1_boy_price=3500.0,
            tier1_girl_price=3000.0,
            tier1_qty=0,
            tier2_boy_price=4000.0,
            tier2_girl_price=3500.0,
            tier2_qty=0,
        )

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

    # ---- helpers -----------------------------------------------------------

    def _create_reservation(self, attendee_names, boys=1, girls=0, status="approved"):
        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=boys,
            girls=girls,
            attendees=attendee_names,
            payment_file_id="proof",
            payment_file_type="photo",
        )
        if status == "approved":
            ok, _msg, approved = self.db.approve_reservation(reservation.id, self.admin_tg_id)
            self.assertTrue(ok)
            return approved
        if status == "rejected":
            ok, _msg, rejected = self.db.reject_reservation(
                reservation.id, admin_tg_id=self.admin_tg_id, admin_note="bad proof"
            )
            self.assertTrue(ok)
            return rejected
        if status == "cancelled":
            self.db.conn.execute(
                "UPDATE reservations SET status = 'cancelled' WHERE id = ?",
                (reservation.id,),
            )
            self.db.conn.commit()
            return self.db.get_reservation(reservation.id)
        return reservation

    def _guard_client(self):
        client = TestClient(self.server.app)
        resp = client.post("/api/guard/login", json={"password": self.guard_password})
        self.assertEqual(resp.status_code, 200, resp.text)
        return client

    def _admin_client(self):
        client = TestClient(self.server.app)
        resp = client.post("/api/admin/login", json={"password": self.admin_password})
        self.assertEqual(resp.status_code, 200, resp.text)
        return client

    # ---- Feature 1: guard role --------------------------------------------

    def test_guard_login_sets_cookie_and_bootstrap(self):
        resp = self.client.post("/api/guard/login", json={"password": self.guard_password})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json().get("role"), "guard")
        self.assertIn("bt_guard_session=", resp.headers.get("set-cookie", ""))
        boot = self.client.get("/api/guard/bootstrap")
        self.assertEqual(boot.status_code, 200, boot.text)
        self.assertEqual(boot.json()["role"], "guard")

    def test_guard_login_wrong_password_rejected(self):
        resp = self.client.post("/api/guard/login", json={"password": "nope"})
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_guard_login_not_configured_returns_503(self):
        os.environ["GUARD_WEB_PASSWORD"] = ""
        server = importlib.reload(self.server)
        try:
            client = TestClient(server.app)
            resp = client.post("/api/guard/login", json={"password": "anything"})
            self.assertEqual(resp.status_code, 503, resp.text)
            self.assertIn("not configured", resp.json()["detail"])
        finally:
            os.environ["GUARD_WEB_PASSWORD"] = self.guard_password
            self.server = importlib.reload(server)
            self.db = self.server.db

    def test_guard_can_lookup_and_checkin(self):
        reservation = self._create_reservation(["Gate Guest"], status="approved")
        token = self.db.list_attendees(reservation.id)[0]["ticket_token"]
        guard = self._guard_client()

        lookup = guard.get("/api/admin/checkin/lookup", params={"token": token})
        self.assertEqual(lookup.status_code, 200, lookup.text)
        self.assertTrue(lookup.json()["ok"])

        checkin = guard.post("/api/admin/checkin", json={"token": token})
        self.assertEqual(checkin.status_code, 200, checkin.text)
        self.assertTrue(checkin.json()["ok"])
        self.assertTrue(checkin.json()["ticket"]["checked_in"])
        # Guard has no tg_id: check-in is attributed to admin_tg_id 0.
        row = self.db.lookup_ticket(token)
        self.assertEqual(int(row["checked_in_by_admin_tg_id"]), 0)

    def test_guard_blocked_on_admin_only_endpoints(self):
        guard = self._guard_client()
        events = guard.get("/api/admin/events")
        self.assertIn(events.status_code, (401, 403), events.text)
        pending = guard.get("/api/admin/reservation/pending")
        self.assertIn(pending.status_code, (401, 403), pending.text)

    def test_guard_logout_invalidates_session(self):
        reservation = self._create_reservation(["Logout Guest"], status="approved")
        token = self.db.list_attendees(reservation.id)[0]["ticket_token"]
        guard = self._guard_client()
        self.assertEqual(
            guard.get("/api/admin/checkin/lookup", params={"token": token}).status_code, 200
        )
        logout = guard.post("/api/guard/logout")
        self.assertEqual(logout.status_code, 200, logout.text)
        after = guard.get("/api/admin/checkin/lookup", params={"token": token})
        self.assertEqual(after.status_code, 401, after.text)

    # ---- Feature 2: invoice PDF + email attachments ------------------------

    def test_build_invoice_pdf_returns_pdf_bytes_with_matching_qr(self):
        reservation = self._create_reservation(
            ["Boy One", "Girl Two"], boys=1, girls=1, status="approved"
        )
        attendees = self.db.list_attendees(reservation.id)
        buyer = self.db.get_user_by_id(self.user_id)
        event = self.db.get_event(self.event_id)

        captured = []
        original_make = self.server.qrcode.make

        def _capture_make(data, *args, **kwargs):
            captured.append(data)
            return original_make(data, *args, **kwargs)

        self.server.qrcode.make = _capture_make
        try:
            pdf = self.server.build_invoice_pdf(reservation, event, buyer, attendees, "Bank Transfer")
        finally:
            self.server.qrcode.make = original_make

        self.assertIsInstance(pdf, (bytes, bytearray))
        self.assertTrue(bytes(pdf).startswith(b"%PDF"))
        self.assertEqual(len(captured), len(attendees))
        for att in attendees:
            expected = self.server._invoice_checkin_url(att["ticket_token"])
            self.assertIn(expected, captured)
            self.assertTrue(expected.endswith("/checkin/" + att["ticket_token"]))

    def test_approval_returns_200_when_email_unconfigured(self):
        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=["Approve Guest"],
            payment_file_id="proof",
            payment_file_type="photo",
        )
        admin = self._admin_client()
        resp = admin.post("/api/admin/reservation/approve", json={"reservation_id": reservation.id})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(self.db.get_reservation(reservation.id).status, "approved")

    def test_send_email_includes_attachment_when_configured(self):
        captured = {}

        def _fake_urlopen(req, timeout=10):
            captured["body"] = req.data

            class _Resp:
                status = 200

                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, *args):
                    return False

            return _Resp()

        orig_urlopen = self.server.urllib.request.urlopen
        orig_key = self.server.RESEND_API_KEY
        orig_from = self.server.RESEND_FROM_EMAIL
        orig_dev = self.server.EMAIL_LOGIN_DEV_MODE
        self.server.urllib.request.urlopen = _fake_urlopen
        self.server.RESEND_API_KEY = "re_test_key"
        self.server.RESEND_FROM_EMAIL = "Budapest Tunderi <noreply@example.invalid>"
        self.server.EMAIL_LOGIN_DEV_MODE = False
        try:
            self.server._send_email(
                "guest@example.invalid",
                "Your Budapest Tunderi invoice",
                "See attached.",
                attachments=[
                    {"filename": "invoice-ABC.pdf", "content_bytes": b"%PDF-1.4 test", "mime": "application/pdf"}
                ],
            )
        finally:
            self.server.urllib.request.urlopen = orig_urlopen
            self.server.RESEND_API_KEY = orig_key
            self.server.RESEND_FROM_EMAIL = orig_from
            self.server.EMAIL_LOGIN_DEV_MODE = orig_dev

        self.assertIn("body", captured)
        payload = json.loads(captured["body"].decode("utf-8"))
        self.assertIn("attachments", payload)
        self.assertEqual(payload["attachments"][0]["filename"], "invoice-ABC.pdf")
        self.assertEqual(
            base64.b64decode(payload["attachments"][0]["content"]), b"%PDF-1.4 test"
        )

    # ---- Feature 3: purchase history --------------------------------------

    def test_purchase_history_includes_cancelled_and_rejected(self):
        self._create_reservation(["Approved One"], status="approved")
        self._create_reservation(["Rejected One"], status="rejected")
        self._create_reservation(["Cancelled One"], status="cancelled")
        admin = self._admin_client()
        resp = admin.get("/api/admin/purchase_history")
        self.assertEqual(resp.status_code, 200, resp.text)
        statuses = {item["status"] for item in resp.json()["items"]}
        self.assertIn("cancelled", statuses)
        self.assertIn("rejected", statuses)
        self.assertIn("approved", statuses)

    def test_purchase_history_search_by_email_and_phone(self):
        self._create_reservation(["Search Guest"], status="approved")
        admin = self._admin_client()

        by_email = admin.get("/api/admin/purchase_history", params={"search": "buyer.person"})
        self.assertEqual(by_email.status_code, 200, by_email.text)
        self.assertTrue(len(by_email.json()["items"]) >= 1)
        self.assertTrue(
            all("buyer.person" in (i["buyer_email"] or "").lower() for i in by_email.json()["items"])
        )

        by_phone = admin.get("/api/admin/purchase_history", params={"search": "111 2222"})
        self.assertEqual(by_phone.status_code, 200, by_phone.text)
        self.assertTrue(len(by_phone.json()["items"]) >= 1)

        no_match = admin.get("/api/admin/purchase_history", params={"search": "zzz-no-such-buyer"})
        self.assertEqual(no_match.status_code, 200, no_match.text)
        self.assertEqual(no_match.json()["items"], [])

    def test_purchase_history_includes_payment_slot_title(self):
        self._create_reservation(["Slot Guest"], status="approved")
        admin = self._admin_client()
        resp = admin.get("/api/admin/purchase_history")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(all("payment_slot_title" in item for item in resp.json()["items"]))

    def test_purchase_history_requires_admin(self):
        anon = TestClient(self.server.app)
        resp = anon.get("/api/admin/purchase_history")
        self.assertEqual(resp.status_code, 401, resp.text)


if __name__ == "__main__":
    unittest.main()
