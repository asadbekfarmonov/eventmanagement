"""Adversarial QA gap tests for Batch A (guard role, invoice PDF, purchase history).

These cover edge cases the implementer's tests left open:
- guard session must NOT leak into any non-checkin admin endpoint (broad sweep),
- guard_web_sessions must be created by the legacy migration path (_migrate_schema),
- approval must stay 200 even when the invoice PDF build raises,
- _send_email must swallow network errors when attachments are present,
- purchase_history search must match tg_id, reservation code and event title,
- purchase_history must reject a guard-only session (admin-only).
"""
import importlib
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class BatchAQaReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "qa_review.db")
        self.admin_tg_id = 7164876915
        self.user_tg_id = 511308234
        self.admin_password = "test-admin-password"
        self.guard_password = "test-guard-password"
        self._env_keys = (
            "DATABASE_PATH", "ADMIN_IDS", "BOT_TOKEN", "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL", "UPLOAD_DIR", "ADMIN_WEB_PASSWORD", "GUARD_WEB_PASSWORD",
            "EMAIL_LOGIN_DEV_MODE", "RESEND_API_KEY", "RESEND_FROM_EMAIL",
            "SESSION_COOKIE_MAX_AGE_SECONDS", "GOOGLE_CLIENT_ID",
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
            title="Gala Night Special",
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

    def _make_reservation(self, names, boys=1, girls=0, status="approved"):
        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=boys,
            girls=girls,
            attendees=names,
            payment_file_id="proof",
            payment_file_type="photo",
        )
        if status == "approved":
            ok, _m, approved = self.db.approve_reservation(reservation.id, self.admin_tg_id)
            self.assertTrue(ok)
            return approved
        return reservation

    # ---- Gap 1: broad guard-leak sweep across every non-checkin admin route ----

    def test_guard_denied_on_all_non_checkin_admin_endpoints(self):
        guard = self._guard_client()
        reservation = self._make_reservation(["Sweep Guest"])
        # (method, path, json_body)
        cases = [
            ("get", "/api/admin/events", None),
            ("get", "/api/admin/guests", None),
            ("get", "/api/admin/reservations", None),
            ("get", "/api/admin/reservation/pending", None),
            ("get", f"/api/admin/payment/totals?event_id={self.event_id}", None),
            ("get", "/api/admin/purchase_history", None),
            ("get", "/api/admin/guest/export_xlsx", None),
            ("get", "/api/admin/bootstrap", None),
            ("post", "/api/admin/event/create_simple", {"title": "x", "event_datetime": "2026-01-01 10:00", "location": "y"}),
            ("post", "/api/admin/event/update", {"event_id": self.event_id, "title": "hacked"}),
            ("post", "/api/admin/event/delete", {"event_id": self.event_id}),
            ("post", "/api/admin/guest/add", {"event_id": self.event_id, "name": "X"}),
            ("post", "/api/admin/guest/remove", {"guest_id": 1}),
            ("post", "/api/admin/carousel/delete", {"image_id": 1}),
            ("post", "/api/admin/reservation/approve", {"reservation_id": reservation.id}),
            ("post", "/api/admin/reservation/reject", {"reservation_id": reservation.id}),
        ]
        for method, path, body in cases:
            resp = getattr(guard, method)(path, json=body) if body is not None else getattr(guard, method)(path)
            # The security property: a guard session must NEVER get a 2xx success on
            # any non-checkin admin route. (401/403 = denied; 422 = body/param rejected
            # by FastAPI before the request is processed. Neither grants access.)
            self.assertFalse(
                200 <= resp.status_code < 300,
                f"guard leaked into {method.upper()} {path} -> {resp.status_code}: {resp.text}",
            )
        # And prove the guard could still do its ONE allowed job meanwhile.
        token = self.db.list_attendees(reservation.id)[0]["ticket_token"]
        self.assertEqual(
            guard.get("/api/admin/checkin/lookup", params={"token": token}).status_code, 200
        )

    def test_guard_cannot_reach_purchase_history(self):
        guard = self._guard_client()
        resp = guard.get("/api/admin/purchase_history")
        self.assertIn(resp.status_code, (401, 403), resp.text)

    # ---- Gap 2: legacy DB migration creates guard_web_sessions ----

    def test_migrate_schema_creates_guard_table_on_legacy_db(self):
        from ticketbot.database import Database

        legacy_path = os.path.join(self.temp_dir.name, "legacy.db")
        legacy = Database(legacy_path)
        # Simulate a DB created before the guard feature existed.
        legacy.conn.execute("DROP TABLE guard_web_sessions")
        legacy.conn.commit()
        cur = legacy.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='guard_web_sessions'"
        )
        self.assertIsNone(cur.fetchone(), "precondition: table should be gone")
        # The migration path must recreate it idempotently.
        legacy._migrate_schema()
        cur = legacy.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='guard_web_sessions'"
        )
        self.assertIsNotNone(cur.fetchone(), "guard_web_sessions not created by _migrate_schema")
        # And the session round-trip works against the migrated table.
        token = legacy.create_guard_web_session()
        self.assertTrue(legacy.is_valid_guard_web_session(token))
        legacy.conn.close()

    # ---- Gap 3: approval stays 200 when PDF build raises ----

    def test_approval_succeeds_when_pdf_build_raises(self):
        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=["Boom Guest"],
            payment_file_id="proof",
            payment_file_type="photo",
        )
        original = self.server.build_invoice_pdf

        def _boom(*args, **kwargs):
            raise RuntimeError("pdf exploded")

        self.server.build_invoice_pdf = _boom
        try:
            admin = self._admin_client()
            resp = admin.post("/api/admin/reservation/approve", json={"reservation_id": reservation.id})
        finally:
            self.server.build_invoice_pdf = original
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(self.db.get_reservation(reservation.id).status, "approved")

    # ---- Gap 4: _send_email swallows network error with attachments present ----

    def test_send_email_swallows_network_error_with_attachments(self):
        def _boom_urlopen(req, timeout=10):
            raise OSError("network down")

        orig_urlopen = self.server.urllib.request.urlopen
        orig_key = self.server.RESEND_API_KEY
        orig_from = self.server.RESEND_FROM_EMAIL
        orig_dev = self.server.EMAIL_LOGIN_DEV_MODE
        self.server.urllib.request.urlopen = _boom_urlopen
        self.server.RESEND_API_KEY = "re_test_key"
        self.server.RESEND_FROM_EMAIL = "Budapest Tunderi <noreply@example.invalid>"
        self.server.EMAIL_LOGIN_DEV_MODE = False
        try:
            # Must not raise.
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

    # ---- Gap 5: purchase_history search by tg_id, code, and event title ----

    def test_purchase_history_search_by_tg_id_code_and_title(self):
        reservation = self._make_reservation(["Match Guest"], status="approved")
        code = reservation.code
        admin = self._admin_client()

        by_tg = admin.get("/api/admin/purchase_history", params={"search": str(self.user_tg_id)})
        self.assertEqual(by_tg.status_code, 200, by_tg.text)
        self.assertTrue(len(by_tg.json()["items"]) >= 1, "no match by tg_id")

        by_code = admin.get("/api/admin/purchase_history", params={"search": code})
        self.assertEqual(by_code.status_code, 200, by_code.text)
        codes = {i["code"] for i in by_code.json()["items"]}
        self.assertIn(code, codes, "no match by reservation code")

        by_title = admin.get("/api/admin/purchase_history", params={"search": "Gala Night"})
        self.assertEqual(by_title.status_code, 200, by_title.text)
        self.assertTrue(len(by_title.json()["items"]) >= 1, "no match by event title")

    def test_purchase_history_limit_is_sanitised(self):
        for i in range(3):
            self._make_reservation([f"Guest {i}"], status="approved")
        admin = self._admin_client()
        # Bogus/negative limit must not error; falls back to a positive default.
        resp = admin.get("/api/admin/purchase_history", params={"limit": -5})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(len(resp.json()["items"]) >= 1)


if __name__ == "__main__":
    unittest.main()
