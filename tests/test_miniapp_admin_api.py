import json
import importlib
import hashlib
import hmac
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from fastapi.testclient import TestClient
from openpyxl import Workbook

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02"
    b"\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f\x00\x02\xeb"
    b"\x01\xf6\xc5\xbb\xc7\x00\x00\x00\x00IEND\xaeB`\x82"
)


class MiniAppAdminApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "miniapp_test.db")
        self.admin_tg_id = 7164876915
        self.user_tg_id = 511308234
        self._env_keys = (
            "DATABASE_PATH",
            "ADMIN_IDS",
            "BOT_TOKEN",
            "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL",
            "UPLOAD_DIR",
            "UPLOAD_MAX_MB",
            "UPLOAD_RETENTION_DAYS",
            "UPLOAD_CLEANUP_INTERVAL_SECONDS",
            "UPLOAD_LINK_TTL_SECONDS",
            "RATE_LIMIT_WINDOW_SECONDS",
            "QUOTE_RATE_LIMIT",
            "BOOKING_RATE_LIMIT",
            "ADMIN_WEB_PASSWORD",
            "EMAIL_LOGIN_DEV_MODE",
            "EMAIL_LOGIN_TTL_SECONDS",
            "EMAIL_LOGIN_RATE_LIMIT",
            "EMAIL_CODE_ATTEMPT_LIMIT",
            "RESEND_API_KEY",
            "RESEND_FROM_EMAIL",
            "LEGACY_WEB_REGISTER_ENABLED",
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
        os.environ["UPLOAD_MAX_MB"] = "5"
        os.environ["UPLOAD_RETENTION_DAYS"] = "7"
        os.environ["UPLOAD_CLEANUP_INTERVAL_SECONDS"] = "3600"
        os.environ["UPLOAD_LINK_TTL_SECONDS"] = "604800"
        os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"
        os.environ["QUOTE_RATE_LIMIT"] = "120"
        os.environ["BOOKING_RATE_LIMIT"] = "12"
        os.environ["ADMIN_WEB_PASSWORD"] = "test-admin-password"
        os.environ["EMAIL_LOGIN_DEV_MODE"] = "1"
        os.environ["EMAIL_LOGIN_TTL_SECONDS"] = "600"
        os.environ["EMAIL_LOGIN_RATE_LIMIT"] = "20"
        os.environ["EMAIL_CODE_ATTEMPT_LIMIT"] = "5"
        os.environ["RESEND_API_KEY"] = ""
        os.environ["RESEND_FROM_EMAIL"] = ""
        os.environ["LEGACY_WEB_REGISTER_ENABLED"] = "0"
        os.environ["SESSION_COOKIE_MAX_AGE_SECONDS"] = "7776000"
        os.environ["GOOGLE_CLIENT_ID"] = ""

        import ticketbot.miniapp_server as miniapp_server

        self.server = importlib.reload(miniapp_server)
        self.client = TestClient(self.server.app)
        self.db = self.server.db

        self.db.upsert_user(self.user_tg_id, "Buyer", "User", "phone")
        user = self.db.get_user(self.user_tg_id)
        self.user_id = user.id
        self.event_id = self.db.create_event(
            title="Test Event",
            event_datetime="2026-03-03 16:00",
            location="Budapest",
            caption="Caption",
            photo_file_id="",
            early_boy_price=2500.0,
            early_girl_price=2500.0,
            early_qty=10,
            tier1_boy_price=3500.0,
            tier1_girl_price=3500.0,
            tier1_qty=0,
            tier2_boy_price=4000.0,
            tier2_girl_price=4000.0,
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

    def _create_reservation(self, attendee_name: str, status: str = "pending_payment_review"):
        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=[attendee_name],
            payment_file_id="proof",
            payment_file_type="photo",
        )
        if status == "approved":
            ok, _msg, approved = self.db.approve_reservation(reservation.id, self.admin_tg_id)
            self.assertTrue(ok)
            return approved
        if status == "pending":
            self.db.conn.execute("UPDATE reservations SET status = 'pending' WHERE id = ?", (reservation.id,))
            self.db.conn.commit()
            return self.db.get_reservation(reservation.id)
        if status == "rejected":
            ok, _msg, rejected = self.db.reject_reservation(
                reservation.id,
                admin_tg_id=self.admin_tg_id,
                admin_note="invalid proof",
            )
            self.assertTrue(ok)
            return rejected
        return reservation

    def _book_with_payment(
        self,
        *,
        tg_id=None,
        event_id=None,
        boys=1,
        girls=0,
        attendees=None,
        discounted_attendee_indexes=None,
        repost_files=None,
        filename="proof.png",
        content=PNG_BYTES,
        mime="image/png",
        terms_accepted="true",
    ):
        names = attendees or ["John Doe"]
        files = [
            (
                "file",
                (
                    filename,
                    content,
                    mime,
                ),
            )
        ]
        for idx, repost_file in (repost_files or {}).items():
            repost_name, repost_content, repost_mime = repost_file
            files.append(
                (
                    f"repost_file_{idx}",
                    (
                        repost_name,
                        repost_content,
                        repost_mime,
                    ),
                )
            )
        return self.client.post(
            "/api/book_with_payment",
            data={
                "tg_id": str(self.user_tg_id if tg_id is None else tg_id),
                "event_id": str(self.event_id if event_id is None else event_id),
                "boys": str(boys),
                "girls": str(girls),
                "attendees": json.dumps(names),
                "discounted_attendee_indexes": json.dumps(discounted_attendee_indexes or []),
                "terms_accepted": terms_accepted,
            },
            files=files,
        )

    def _telegram_init_data(self, tg_id: int, bot_token: str = "test-token", auth_date: int = None) -> str:
        user_json = json.dumps({"id": tg_id, "first_name": "Admin"}, separators=(",", ":"))
        pairs = {
            "auth_date": str(int(auth_date or time.time())),
            "query_id": "test-query",
            "user": user_json,
        }
        data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        signature = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        return "&".join(f"{key}={quote(value)}" for key, value in [*pairs.items(), ("hash", signature)])

    def test_admin_page_redirects_to_current_mini_app_admin_mode(self):
        response = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers.get("location"), "/?open_admin=1")

    def test_admin_api_requires_verified_telegram_init_data_when_bot_token_is_configured(self):
        old_env = {key: os.environ.get(key) for key in self._env_keys}
        auth_dir = tempfile.TemporaryDirectory()
        auth_client = None
        try:
            os.environ["DATABASE_PATH"] = os.path.join(auth_dir.name, "auth.db")
            os.environ["ADMIN_IDS"] = str(self.admin_tg_id)
            os.environ["BOT_TOKEN"] = "test-token"
            os.environ["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "0"
            os.environ["WEB_APP_URL"] = "https://example.invalid"
            os.environ["UPLOAD_DIR"] = os.path.join(auth_dir.name, "uploads")
            os.environ["UPLOAD_MAX_MB"] = "5"
            os.environ["UPLOAD_RETENTION_DAYS"] = "7"
            os.environ["UPLOAD_CLEANUP_INTERVAL_SECONDS"] = "3600"

            auth_server = importlib.reload(self.server)
            auth_client = TestClient(auth_server.app)

            forged = auth_client.get("/api/admin/bootstrap", params={"tg_id": self.admin_tg_id})
            self.assertEqual(forged.status_code, 401, forged.text)

            valid = auth_client.get(
                "/api/admin/bootstrap",
                params={"tg_id": self.admin_tg_id},
                headers={"X-Telegram-Init-Data": self._telegram_init_data(self.admin_tg_id)},
            )
            self.assertEqual(valid.status_code, 200, valid.text)

            mismatch = auth_client.get(
                "/api/admin/bootstrap",
                params={"tg_id": self.admin_tg_id},
                headers={"X-Telegram-Init-Data": self._telegram_init_data(self.user_tg_id)},
            )
            self.assertEqual(mismatch.status_code, 403, mismatch.text)
        finally:
            if auth_client is not None:
                auth_client.close()
            auth_dir.cleanup()
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            self.server = importlib.reload(self.server)

    def test_logo_static_file_is_served(self):
        response = self.client.get("/static/logo.png")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("content-type", "").startswith("image/png"))
        self.assertGreater(len(response.content), 1000)

    def test_frontend_assets_are_not_cached(self):
        index_response = self.client.get("/")
        self.assertEqual(index_response.status_code, 200)
        self.assertEqual(index_response.headers.get("cache-control"), "no-store, max-age=0")
        self.assertIn("/static/styles.css?v=20260818a", index_response.text)
        self.assertIn("/static/app.js?v=20260818a", index_response.text)
        self.assertIn('/static/logo.png?v=20260818b', index_response.text)
        self.assertNotIn("Signed in with", index_response.text)

        js_response = self.client.get("/static/app.js")
        self.assertEqual(js_response.status_code, 200)
        self.assertEqual(js_response.headers.get("cache-control"), "no-store, max-age=0")

    def test_static_images_are_cached_immutable(self):
        logo_response = self.client.get("/static/logo.png")
        self.assertEqual(logo_response.status_code, 200)
        self.assertEqual(
            logo_response.headers.get("cache-control"),
            "public, max-age=31536000, immutable",
        )
        # HTML and JS keep the intentional no-store policy for instant deploys.
        self.assertEqual(
            self.client.get("/").headers.get("cache-control"), "no-store, max-age=0"
        )
        self.assertEqual(
            self.client.get("/static/app.js").headers.get("cache-control"),
            "no-store, max-age=0",
        )

    def test_tg_init_script_is_served_and_sdk_is_conditional(self):
        response = self.client.get("/static/tg-init.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers.get("content-type", ""))
        self.assertIn("telegram-web-app.js", response.text)
        # tg-init.js is same-origin code, so it keeps the no-store policy.
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        # A plain website visitor must not be forced to fetch telegram.org.
        index_text = self.client.get("/").text
        self.assertNotIn("https://telegram.org/js/telegram-web-app.js", index_text)
        self.assertIn("/static/tg-init.js", index_text)

    def test_website_registration_can_book_and_read_tickets_without_telegram(self):
        start_resp = self.client.post(
            "/api/web/login/start",
            json={
                "name": "Web",
                "surname": "Guest",
                "email": "web.guest@example.invalid",
                "phone": "+36 20 123 4567",
            },
        )
        self.assertEqual(start_resp.status_code, 200, start_resp.text)
        code = start_resp.json()["dev_code"]

        wrong_resp = self.client.post(
            "/api/web/login/verify",
            json={"email": "web.guest@example.invalid", "code": "000000"},
        )
        self.assertEqual(wrong_resp.status_code, 400, wrong_resp.text)

        verify_resp = self.client.post(
            "/api/web/login/verify",
            json={"email": "web.guest@example.invalid", "code": code},
        )
        self.assertEqual(verify_resp.status_code, 200, verify_resp.text)
        self.assertIn("bt_web_session=", verify_resp.headers.get("set-cookie", ""))
        self.assertNotIn("session_token", verify_resp.json())

        me_resp = self.client.get("/api/me")
        self.assertEqual(me_resp.status_code, 200, me_resp.text)
        self.assertEqual(me_resp.json()["profile"]["source"], "website")
        self.assertEqual(me_resp.json()["profile"]["email"], "web.guest@example.invalid")

        update_resp = self.client.put(
            "/api/web/profile",
            json={"name": "Web", "surname": "Guest", "phone": "+36 20 999 8888"},
        )
        self.assertEqual(update_resp.status_code, 200, update_resp.text)
        self.assertEqual(update_resp.json()["profile"]["phone"], "+36 20 999 8888")

        email_start_resp = self.client.post(
            "/api/web/email/start",
            json={"email": "new.web.guest@example.invalid"},
        )
        self.assertEqual(email_start_resp.status_code, 200, email_start_resp.text)
        email_code = email_start_resp.json()["dev_code"]

        wrong_email_resp = self.client.post(
            "/api/web/email/verify",
            json={"email": "new.web.guest@example.invalid", "code": "000000"},
        )
        self.assertEqual(wrong_email_resp.status_code, 400, wrong_email_resp.text)

        email_verify_resp = self.client.post(
            "/api/web/email/verify",
            json={"email": "new.web.guest@example.invalid", "code": email_code},
        )
        self.assertEqual(email_verify_resp.status_code, 200, email_verify_resp.text)
        self.assertEqual(email_verify_resp.json()["profile"]["email"], "new.web.guest@example.invalid")

        cookie_me_resp = self.client.get("/api/me")
        self.assertEqual(cookie_me_resp.status_code, 200, cookie_me_resp.text)
        self.assertEqual(cookie_me_resp.json()["profile"]["email"], "new.web.guest@example.invalid")

        files = [("file", ("proof.png", PNG_BYTES, "image/png"))]
        booking_resp = self.client.post(
            "/api/book_with_payment",
            data={
                "event_id": str(self.event_id),
                "boys": "1",
                "girls": "0",
                "attendees": json.dumps(["Web Guest"]),
                "discounted_attendee_indexes": "[]",
                "terms_accepted": "true",
            },
            files=files,
        )
        self.assertEqual(booking_resp.status_code, 200, booking_resp.text)

        tickets_resp = self.client.get("/api/my_tickets")
        self.assertEqual(tickets_resp.status_code, 200, tickets_resp.text)
        items = tickets_resp.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["attendees"], ["Web Guest"])

    def test_website_admin_login_can_access_admin_apis(self):
        login_resp = self.client.post(
            "/api/admin/login",
            json={"password": "test-admin-password"},
        )
        self.assertEqual(login_resp.status_code, 200, login_resp.text)
        self.assertIn("bt_admin_session=", login_resp.headers.get("set-cookie", ""))
        self.assertNotIn("admin_session", login_resp.json())

        bootstrap_resp = self.client.get("/api/admin/bootstrap")
        self.assertEqual(bootstrap_resp.status_code, 200, bootstrap_resp.text)
        self.assertEqual(bootstrap_resp.json()["source"], "website")

        events_resp = self.client.get("/api/admin/events")
        self.assertEqual(events_resp.status_code, 200, events_resp.text)
        self.assertEqual(len(events_resp.json()["items"]), 1)

        cookie_events_resp = self.client.get("/api/admin/events")
        self.assertEqual(cookie_events_resp.status_code, 200, cookie_events_resp.text)
        self.assertEqual(len(cookie_events_resp.json()["items"]), 1)

    def test_user_web_session_cannot_access_admin_apis(self):
        start_resp = self.client.post(
            "/api/web/login/start",
            json={
                "name": "Not",
                "surname": "Admin",
                "email": "not.admin@example.invalid",
                "phone": "+36 20 777 0000",
            },
        )
        self.assertEqual(start_resp.status_code, 200, start_resp.text)
        verify_resp = self.client.post(
            "/api/web/login/verify",
            json={"email": "not.admin@example.invalid", "code": start_resp.json()["dev_code"]},
        )
        self.assertEqual(verify_resp.status_code, 200, verify_resp.text)
        self.assertNotIn("session_token", verify_resp.json())

        response = self.client.get("/api/admin/events")
        self.assertEqual(response.status_code, 401, response.text)

    def test_expired_web_session_cookie_is_rejected(self):
        start_resp = self.client.post(
            "/api/web/login/start",
            json={
                "name": "Old",
                "surname": "Session",
                "email": "old.session@example.invalid",
                "phone": "+36 20 777 1111",
            },
        )
        self.assertEqual(start_resp.status_code, 200, start_resp.text)
        verify_resp = self.client.post(
            "/api/web/login/verify",
            json={"email": "old.session@example.invalid", "code": start_resp.json()["dev_code"]},
        )
        self.assertEqual(verify_resp.status_code, 200, verify_resp.text)
        expired_at = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        self.db.conn.execute("UPDATE web_sessions SET created_at = ?", (expired_at,))
        self.db.conn.commit()

        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 401, response.text)

    def test_expired_admin_session_cookie_is_rejected(self):
        login_resp = self.client.post(
            "/api/admin/login",
            json={"password": "test-admin-password"},
        )
        self.assertEqual(login_resp.status_code, 200, login_resp.text)
        expired_at = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        self.db.conn.execute("UPDATE admin_web_sessions SET created_at = ?", (expired_at,))
        self.db.conn.commit()

        response = self.client.get("/api/admin/events")
        self.assertEqual(response.status_code, 401, response.text)

    def test_google_login_is_disabled_without_client_id(self):
        config_resp = self.client.get("/api/web/auth_config")
        self.assertEqual(config_resp.status_code, 200, config_resp.text)
        self.assertEqual(config_resp.json()["google_client_id"], "")

        response = self.client.post(
            "/api/web/login/google",
            json={"credential": "x" * 40, "phone": "+36 20 111 1111"},
        )
        self.assertEqual(response.status_code, 503, response.text)

    def test_booking_without_telegram_or_web_session_is_rejected(self):
        response = self.client.post(
            "/api/book_with_payment",
            data={
                "event_id": str(self.event_id),
                "boys": "1",
                "girls": "0",
                "attendees": json.dumps(["No Session"]),
                "discounted_attendee_indexes": "[]",
                "terms_accepted": "true",
            },
            files=[("file", ("proof.png", PNG_BYTES, "image/png"))],
        )
        self.assertEqual(response.status_code, 401, response.text)

    def _login_admin_web(self):
        resp = self.client.post("/api/admin/login", json={"password": "test-admin-password"})
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp

    def test_admin_pending_list_resigns_external_proof_and_notes_telegram(self):
        self._login_admin_web()

        booking = self._book_with_payment(boys=1, girls=0, attendees=["Web Guest"])
        self.assertEqual(booking.status_code, 200, booking.text)
        ext_res = self.db.get_reservation_by_code(booking.json()["code"])
        self.assertEqual(ext_res.payment_file_type, "external")
        upload_name = Path(urlparse(ext_res.payment_file_id).path).name

        # Corrupt the stored signed link so only a fresh re-sign yields a working URL.
        self.db.conn.execute(
            "UPDATE reservations SET payment_file_id = ? WHERE id = ?",
            (f"https://example.invalid/uploads/{upload_name}?expires=1&token=deadbeef", ext_res.id),
        )
        self.db.conn.commit()

        tg_res = self._create_reservation("Telegram Guest")

        resp = self.client.get("/api/admin/reservation/pending")
        self.assertEqual(resp.status_code, 200, resp.text)
        items = {item["reservation_id"]: item for item in resp.json()["items"]}
        self.assertIn(ext_res.id, items)
        self.assertIn(tg_res.id, items)

        ext_item = items[ext_res.id]
        self.assertIsNotNone(ext_item["proof_url"])
        self.assertIn(f"/uploads/{upload_name}", ext_item["proof_url"])
        self.assertEqual(ext_item["attendees"], ["Web Guest"])
        parsed = urlparse(ext_item["proof_url"])
        fetch = self.client.get(f"{parsed.path}?{parsed.query}")
        self.assertEqual(fetch.status_code, 200, fetch.text)

        tg_item = items[tg_res.id]
        self.assertIsNone(tg_item["proof_url"])
        self.assertEqual(tg_item["proof_note"], "Payment proof was sent in Telegram.")

    def test_admin_pending_list_includes_fresh_repost_proof_urls(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "repost_discount_enabled": 1,
                "repost_discount_amount": 1000,
            },
        )

        # External repost proof via the real web booking flow (writes a real file).
        booking = self._book_with_payment(
            boys=1,
            girls=0,
            attendees=["Repost Guest"],
            discounted_attendee_indexes=[0],
            repost_files={0: ("repost-0.png", PNG_BYTES, "image/png")},
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(booking.status_code, 200, booking.text)
        ext_res = self.db.get_reservation_by_code(booking.json()["code"])
        ext_attendees = self.db.list_attendees(ext_res.id)
        self.assertEqual(ext_attendees[0]["repost_proof_file_type"], "external")
        upload_name = Path(urlparse(ext_attendees[0]["repost_proof_file_id"]).path).name

        # Corrupt the stored signed link so only a fresh re-sign yields a working URL.
        self.db.conn.execute(
            "UPDATE attendees SET repost_proof_file_id = ? WHERE id = ?",
            (
                f"https://example.invalid/uploads/{upload_name}?expires=1&token=deadbeef",
                ext_attendees[0]["id"],
            ),
        )
        self.db.conn.commit()

        # Non-external repost proof (sent in Telegram) must be omitted from the web review.
        tg_res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=["Telegram Repost Guest"],
            payment_file_id="proof",
            payment_file_type="photo",
            discounted_attendee_indexes=[0],
            repost_proofs_by_index={0: ("tg-repost-file-id", "photo")},
        )

        self._login_admin_web()
        resp = self.client.get("/api/admin/reservation/pending")
        self.assertEqual(resp.status_code, 200, resp.text)
        items = {item["reservation_id"]: item for item in resp.json()["items"]}
        self.assertIn(ext_res.id, items)
        self.assertIn(tg_res.id, items)

        ext_item = items[ext_res.id]
        self.assertEqual(len(ext_item["repost_proofs"]), 1)
        proof = ext_item["repost_proofs"][0]
        self.assertEqual(proof["full_name"], "Repost Guest")
        self.assertIsNotNone(proof["url"])
        self.assertIn(f"/uploads/{upload_name}", proof["url"])
        parsed = urlparse(proof["url"])
        fetch = self.client.get(f"{parsed.path}?{parsed.query}")
        self.assertEqual(fetch.status_code, 200, fetch.text)

        tg_item = items[tg_res.id]
        self.assertEqual(tg_item["repost_proofs"], [])

    def test_admin_pending_omits_absent_and_unusable_repost_proofs(self):
        """M2 gap: repost_discount_applied but no usable external file -> omitted,
        never surfaced as a null/broken entry."""
        self.db.set_event_fields(
            self.event_id,
            {"repost_discount_enabled": 1, "repost_discount_amount": 1000},
        )

        # (a) External repost type but EMPTY stored file id -> no filename -> omit.
        empty_res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=["Empty Proof Guest"],
            payment_file_id="proof",
            payment_file_type="photo",
            discounted_attendee_indexes=[0],
            repost_proofs_by_index={0: ("", "external")},
        )

        # (b) External repost type but the stored value is not an /uploads/ path -> omit.
        badpath_res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=["Bad Path Guest"],
            payment_file_id="proof",
            payment_file_type="photo",
            discounted_attendee_indexes=[0],
            repost_proofs_by_index={0: ("https://evil.example/not-uploads/x.png", "external")},
        )

        self._login_admin_web()
        resp = self.client.get("/api/admin/reservation/pending")
        self.assertEqual(resp.status_code, 200, resp.text)
        items = {item["reservation_id"]: item for item in resp.json()["items"]}

        self.assertIn(empty_res.id, items)
        self.assertIn(badpath_res.id, items)
        # Key is always present and is an empty list (never null / never a broken entry).
        self.assertEqual(items[empty_res.id]["repost_proofs"], [])
        self.assertEqual(items[badpath_res.id]["repost_proofs"], [])

    def test_admin_approve_moves_pending_to_approved_and_requires_session(self):
        reservation = self._create_reservation("Approve Guest")

        no_auth = self.client.post(
            "/api/admin/reservation/approve",
            json={"reservation_id": reservation.id},
        )
        self.assertEqual(no_auth.status_code, 401, no_auth.text)
        self.assertEqual(self.db.get_reservation(reservation.id).status, "pending_payment_review")

        self._login_admin_web()
        approve = self.client.post(
            "/api/admin/reservation/approve",
            json={"reservation_id": reservation.id},
        )
        self.assertEqual(approve.status_code, 200, approve.text)
        self.assertTrue(approve.json()["ok"])
        self.assertEqual(self.db.get_reservation(reservation.id).status, "approved")

    def test_admin_reject_requires_note_and_releases_hold(self):
        event_before = self.db.get_event(self.event_id)
        reservation = self._create_reservation("Reject Guest")
        event_held = self.db.get_event(self.event_id)
        self.assertEqual(event_held.early_bird_qty, event_before.early_bird_qty - 1)

        self._login_admin_web()

        missing = self.client.post(
            "/api/admin/reservation/reject",
            json={"reservation_id": reservation.id},
        )
        self.assertEqual(missing.status_code, 400, missing.text)
        self.assertEqual(missing.json()["detail"], "Rejection note is required.")

        blank = self.client.post(
            "/api/admin/reservation/reject",
            json={"reservation_id": reservation.id, "note": "   "},
        )
        self.assertEqual(blank.status_code, 400, blank.text)
        self.assertEqual(self.db.get_reservation(reservation.id).status, "pending_payment_review")

        ok = self.client.post(
            "/api/admin/reservation/reject",
            json={"reservation_id": reservation.id, "note": "Blurry proof"},
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        rejected = self.db.get_reservation(reservation.id)
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.admin_note, "Blurry proof")
        event_after = self.db.get_event(self.event_id)
        self.assertEqual(event_after.early_bird_qty, event_before.early_bird_qty)

    def test_admin_logout_invalidates_session(self):
        self._login_admin_web()
        self.assertEqual(self.client.get("/api/admin/events").status_code, 200)

        logout = self.client.post("/api/admin/logout")
        self.assertEqual(logout.status_code, 200, logout.text)
        self.assertTrue(logout.json()["ok"])

        after = self.client.get("/api/admin/events")
        self.assertEqual(after.status_code, 401, after.text)

    def test_admin_guest_rename_and_remove_api(self):
        reservation = self._create_reservation("Azat Jolamanov", status="approved")
        attendee_id = self.db.list_attendees(reservation.id)[0]["id"]

        rename_resp = self.client.post(
            "/api/admin/guest/rename",
            json={
                "tg_id": self.admin_tg_id,
                "attendee_id": attendee_id,
                "full_name": "Renamed Guest",
            },
        )
        self.assertEqual(rename_resp.status_code, 200, rename_resp.text)

        remove_resp = self.client.post(
            "/api/admin/guest/remove",
            json={
                "tg_id": self.admin_tg_id,
                "attendee_id": attendee_id,
            },
        )
        self.assertEqual(remove_resp.status_code, 200, remove_resp.text)
        updated = self.db.get_reservation(reservation.id)
        self.assertEqual(updated.status, "cancelled")
        self.assertEqual(updated.quantity, 0)

    def test_quote_api_spills_over_to_next_tier(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "early_qty": 3,
                "tier1_qty": 5,
                "tier2_qty": 0,
            },
        )
        response = self.client.post(
            "/api/quote",
            json={
                "event_id": self.event_id,
                "boys": 3,
                "girls": 2,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["quantity"], 5)
        self.assertAlmostEqual(payload["total_price"], 14500.0)
        self.assertEqual([row["tier_key"] for row in payload["breakdown"]], ["early", "tier1"])
        self.assertEqual(payload["breakdown"][0]["count"], 3)
        self.assertEqual(payload["breakdown"][1]["count"], 2)

    def test_quote_api_applies_group_offer_discount(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "girls_group_offer_enabled": 1,
                "boys_group_offer_enabled": 1,
            },
        )
        response = self.client.post(
            "/api/quote",
            json={
                "event_id": self.event_id,
                "boys": 4,
                "girls": 3,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertAlmostEqual(payload["base_total_price"], 17500.0)
        self.assertEqual(payload["girls_group_free_count"], 1)
        self.assertEqual(payload["boys_group_free_count"], 1)
        self.assertAlmostEqual(payload["group_discount_amount"], 5000.0)
        self.assertAlmostEqual(payload["total_price"], 12500.0)

    def test_quote_api_rejects_when_exceeding_total_remaining(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "early_qty": 1,
                "tier1_qty": 1,
                "tier2_qty": 0,
            },
        )
        response = self.client.post(
            "/api/quote",
            json={
                "event_id": self.event_id,
                "boys": 3,
                "girls": 0,
            },
        )
        self.assertEqual(response.status_code, 409, response.text)

    def test_quote_api_rate_limit(self):
        self.server.QUOTE_RATE_LIMIT = 1
        first = self.client.post(
            "/api/quote",
            json={
                "event_id": self.event_id,
                "boys": 1,
                "girls": 0,
            },
        )
        self.assertEqual(first.status_code, 200, first.text)

        second = self.client.post(
            "/api/quote",
            json={
                "event_id": self.event_id,
                "boys": 1,
                "girls": 0,
            },
        )
        self.assertEqual(second.status_code, 429, second.text)
        self.assertIn("Too many requests", second.json().get("detail", ""))

    def test_admin_guest_remove_allows_legacy_pending_status(self):
        reservation = self._create_reservation("Legacy Pending", status="pending")
        attendee_id = self.db.list_attendees(reservation.id)[0]["id"]

        remove_resp = self.client.post(
            "/api/admin/guest/remove",
            json={
                "tg_id": self.admin_tg_id,
                "attendee_id": attendee_id,
            },
        )
        self.assertEqual(remove_resp.status_code, 200, remove_resp.text)
        updated = self.db.get_reservation(reservation.id)
        self.assertEqual(updated.status, "cancelled")

    def test_admin_guest_remove_allows_status_with_case_and_spaces(self):
        reservation = self._create_reservation("Legacy Approved", status="pending_payment_review")
        self.db.conn.execute("UPDATE reservations SET status = ' Approved ' WHERE id = ?", (reservation.id,))
        self.db.conn.commit()
        attendee_id = self.db.list_attendees(reservation.id)[0]["id"]

        remove_resp = self.client.post(
            "/api/admin/guest/remove",
            json={
                "tg_id": self.admin_tg_id,
                "attendee_id": attendee_id,
            },
        )
        self.assertEqual(remove_resp.status_code, 200, remove_resp.text)
        updated = self.db.get_reservation(reservation.id)
        self.assertEqual(updated.status, "cancelled")

    def test_admin_guest_remove_rejected_hard_deletes_reservation(self):
        reservation = self._create_reservation("Rejected Guest", status="rejected")
        attendee_id = self.db.list_attendees(reservation.id)[0]["id"]

        remove_resp = self.client.post(
            "/api/admin/guest/remove",
            json={
                "tg_id": self.admin_tg_id,
                "attendee_id": attendee_id,
            },
        )
        self.assertEqual(remove_resp.status_code, 200, remove_resp.text)
        row = self.db.conn.execute(
            "SELECT id FROM reservations WHERE id = ?",
            (reservation.id,),
        ).fetchone()
        self.assertIsNone(row)

    def test_import_xlsx_reads_first_two_columns_and_allows_missing_surname(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "early_qty": 10,
                "tier1_qty": 0,
                "tier2_qty": 0,
            },
        )
        wb = Workbook()
        ws = wb.active
        ws.append(["name", "surname"])
        ws.append(["Horváth", "Tamás"])
        ws.append(["Györfi", "Ádám"])
        ws.append(["SingleNameOnly", None])
        ws.append(["Nigar Bayramova", None])  # should split from col A

        payload = BytesIO()
        wb.save(payload)
        payload.seek(0)

        response = self.client.post(
            "/api/admin/guest/import_xlsx",
            data={
                "tg_id": str(self.admin_tg_id),
                "event_id": str(self.event_id),
            },
            files={
                "file": (
                    "people.xlsx",
                    payload.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["added"], 4)
        self.assertEqual(body["skipped"], 0)

        pairs = self.db.list_guest_name_pairs()
        self.assertIn(("Horváth", "Tamás"), pairs)
        self.assertIn(("Györfi", "Ádám"), pairs)
        self.assertIn(("SingleNameOnly", ""), pairs)
        self.assertIn(("Nigar", "Bayramova"), pairs)
        event = self.db.get_event(self.event_id)
        self.assertEqual(event.early_bird_qty, 10)

        guests_resp = self.client.get(
            "/api/admin/guests",
            params={"tg_id": self.admin_tg_id, "search": "horváth", "limit": 20},
        )
        self.assertEqual(guests_resp.status_code, 200, guests_resp.text)
        guests = guests_resp.json().get("items", [])
        self.assertTrue(any(item.get("full_name") == "Horváth Tamás" for item in guests))

    def test_import_xlsx_rejects_large_upload(self):
        response = self.client.post(
            "/api/admin/guest/import_xlsx",
            data={
                "tg_id": str(self.admin_tg_id),
                "event_id": str(self.event_id),
            },
            files={
                "file": (
                    "people.xlsx",
                    b"x" * (5 * 1024 * 1024 + 1),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        self.assertEqual(response.status_code, 413, response.text)
        self.assertIn("Max allowed size", response.json().get("detail", ""))

    def test_admin_guests_without_limit_returns_all_rows(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["name", "surname"])
        for i in range(45):
            ws.append([f"Name{i}", f"Surname{i}"])
        payload = BytesIO()
        wb.save(payload)
        payload.seek(0)

        import_resp = self.client.post(
            "/api/admin/guest/import_xlsx",
            data={
                "tg_id": str(self.admin_tg_id),
                "event_id": str(self.event_id),
            },
            files={
                "file": (
                    "bulk.xlsx",
                    payload.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        self.assertEqual(import_resp.status_code, 200, import_resp.text)
        self.assertEqual(import_resp.json().get("added"), 45)

        all_resp = self.client.get(
            "/api/admin/guests",
            params={"tg_id": self.admin_tg_id},
        )
        self.assertEqual(all_resp.status_code, 200, all_resp.text)
        self.assertEqual(len(all_resp.json().get("items", [])), 45)

        limited_resp = self.client.get(
            "/api/admin/guests",
            params={"tg_id": self.admin_tg_id, "limit": 10},
        )
        self.assertEqual(limited_resp.status_code, 200, limited_resp.text)
        self.assertEqual(len(limited_resp.json().get("items", [])), 10)

    def test_admin_can_delete_event_with_related_reservations_and_attendees(self):
        reservation = self._create_reservation("Delete Me", status="approved")
        attendees_before = self.db.conn.execute("SELECT COUNT(*) FROM attendees").fetchone()[0]
        reservations_before = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertGreaterEqual(attendees_before, 1)
        self.assertGreaterEqual(reservations_before, 1)

        resp = self.client.post(
            "/api/admin/event/delete",
            json={
                "tg_id": self.admin_tg_id,
                "event_id": self.event_id,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("deleted", {}).get("events"), 1)
        self.assertGreaterEqual(data.get("deleted", {}).get("reservations", 0), 1)
        self.assertGreaterEqual(data.get("deleted", {}).get("attendees", 0), 1)

        self.assertIsNone(self.db.get_event(self.event_id))
        attendees_after = self.db.conn.execute("SELECT COUNT(*) FROM attendees").fetchone()[0]
        reservations_after = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(attendees_after, 0)
        self.assertEqual(reservations_after, 0)

    def test_book_with_payment_rejects_large_upload(self):
        payload = b"x" * (5 * 1024 * 1024 + 1)
        response = self.client.post(
            "/api/book_with_payment",
            data={
                "tg_id": str(self.user_tg_id),
                "event_id": str(self.event_id),
                "boys": "1",
                "girls": "0",
                "attendees": '["John Doe"]',
                "terms_accepted": "true",
            },
            files={
                "file": (
                    "proof.pdf",
                    payload,
                    "application/pdf",
                )
            },
        )
        self.assertEqual(response.status_code, 413, response.text)
        self.assertIn("Max allowed size", response.json().get("detail", ""))

    def test_book_with_payment_creates_pending_reservation_and_lists_ticket(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "early_qty": 2,
                "tier1_qty": 5,
                "tier2_qty": 0,
            },
        )
        response = self._book_with_payment(
            boys=2,
            girls=1,
            attendees=["John Doe", "Jane Doe", "Alex Doe"],
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("status"), "pending_payment_review")
        code = body.get("code")
        self.assertTrue(code)

        reservation = self.db.get_reservation_by_code(code)
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.quantity, 3)
        self.assertEqual(reservation.status, "pending_payment_review")
        self.assertAlmostEqual(reservation.total_price, 8500.0)
        self.assertEqual(reservation.payment_file_type, "external")
        self.assertTrue(reservation.payment_file_id.startswith("https://example.invalid/uploads/"))

        upload_name = Path(urlparse(reservation.payment_file_id).path).name
        self.assertTrue(upload_name)
        self.assertTrue(Path(os.environ["UPLOAD_DIR"], upload_name).exists())
        parsed_upload = urlparse(reservation.payment_file_id)
        signed_params = parse_qs(parsed_upload.query)
        self.assertIn("expires", signed_params)
        self.assertIn("token", signed_params)

        signed_upload_resp = self.client.get(f"{parsed_upload.path}?{parsed_upload.query}")
        self.assertEqual(signed_upload_resp.status_code, 200, signed_upload_resp.text)
        self.assertTrue(signed_upload_resp.headers.get("content-type", "").startswith("image/png"))

        unsigned_upload_resp = self.client.get(parsed_upload.path)
        self.assertIn(unsigned_upload_resp.status_code, {403, 422})

        bad_signed_upload_resp = self.client.get(f"{parsed_upload.path}?expires={signed_params['expires'][0]}&token=bad")
        self.assertEqual(bad_signed_upload_resp.status_code, 403)

        event_after = self.db.get_event(self.event_id)
        self.assertEqual(event_after.early_bird_qty, 0)
        self.assertEqual(event_after.regular_tier1_qty, 4)

        attendees = self.db.list_attendees(reservation.id)
        self.assertEqual([row["ticket_tier"] for row in attendees], ["early", "early", "tier1"])

        tickets_resp = self.client.get(
            "/api/my_tickets",
            params={"tg_id": self.user_tg_id},
        )
        self.assertEqual(tickets_resp.status_code, 200, tickets_resp.text)
        items = tickets_resp.json().get("items", [])
        item = next((x for x in items if x.get("code") == code), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["status"], "pending_payment_review")
        self.assertAlmostEqual(item["total_price"], 8500.0)
        self.assertEqual(item["attendees"], ["John Doe", "Jane Doe", "Alex Doe"])

    def test_approved_ticket_returns_qr_and_admin_can_check_in_once(self):
        reservation = self._create_reservation("Door Guest", status="approved")
        attendee = self.db.list_attendees(reservation.id)[0]
        self.assertTrue(attendee["ticket_token"])

        tickets_resp = self.client.get("/api/my_tickets", params={"tg_id": self.user_tg_id})
        self.assertEqual(tickets_resp.status_code, 200, tickets_resp.text)
        ticket = tickets_resp.json()["items"][0]["tickets"][0]
        self.assertEqual(ticket["full_name"], "Door Guest")
        self.assertFalse(ticket["checked_in"])
        self.assertIn("/api/tickets/", ticket["qr_url"])

        qr_resp = self.client.get(ticket["qr_url"], params={"tg_id": self.user_tg_id})
        self.assertEqual(qr_resp.status_code, 200, qr_resp.text)
        self.assertEqual(qr_resp.headers.get("content-type"), "image/png")
        self.assertTrue(qr_resp.content.startswith(b"\x89PNG\r\n\x1a\n"))

        lookup_resp = self.client.get(
            "/api/admin/checkin/lookup",
            params={"tg_id": self.admin_tg_id, "token": f"https://example.invalid/checkin/{attendee['ticket_token']}"},
        )
        self.assertEqual(lookup_resp.status_code, 200, lookup_resp.text)
        self.assertEqual(lookup_resp.json()["ticket"]["full_name"], "Door Guest")
        self.assertFalse(lookup_resp.json()["ticket"]["checked_in"])

        checkin_resp = self.client.post(
            "/api/admin/checkin",
            json={"tg_id": self.admin_tg_id, "token": attendee["ticket_token"]},
        )
        self.assertEqual(checkin_resp.status_code, 200, checkin_resp.text)
        self.assertTrue(checkin_resp.json()["ok"])
        self.assertTrue(checkin_resp.json()["ticket"]["checked_in"])

        duplicate_resp = self.client.post(
            "/api/admin/checkin",
            json={"tg_id": self.admin_tg_id, "token": attendee["ticket_token"]},
        )
        self.assertEqual(duplicate_resp.status_code, 200, duplicate_resp.text)
        self.assertFalse(duplicate_resp.json()["ok"])
        self.assertIn("already checked in", duplicate_resp.json()["message"])

    def test_checkin_endpoints_reject_non_admin(self):
        reservation = self._create_reservation("Gate Crasher", status="approved")
        attendee = self.db.list_attendees(reservation.id)[0]
        token = attendee["ticket_token"]

        lookup_resp = self.client.get(
            "/api/admin/checkin/lookup",
            params={"tg_id": self.user_tg_id, "token": token},
        )
        self.assertEqual(lookup_resp.status_code, 403, lookup_resp.text)

        checkin_resp = self.client.post(
            "/api/admin/checkin",
            json={"tg_id": self.user_tg_id, "token": token},
        )
        self.assertEqual(checkin_resp.status_code, 403, checkin_resp.text)

        # The ticket must remain not checked-in after the blocked attempts.
        admin_lookup = self.client.get(
            "/api/admin/checkin/lookup",
            params={"tg_id": self.admin_tg_id, "token": token},
        )
        self.assertEqual(admin_lookup.status_code, 200, admin_lookup.text)
        self.assertFalse(admin_lookup.json()["ticket"]["checked_in"])

    def test_jsqr_scanner_fallback_is_self_hosted_and_served(self):
        response = self.client.get("/static/jsqr.js")
        self.assertEqual(response.status_code, 200, response.text)
        content_type = response.headers.get("content-type", "")
        self.assertTrue(
            "javascript" in content_type or "ecmascript" in content_type,
            content_type,
        )
        # A real QR decoder is far larger than a stub; guard against truncation.
        self.assertGreater(len(response.content), 50000)
        self.assertIn("jsQR", response.text)
        # .js keeps the intentional no-store policy so deploys take effect.
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")

    def test_pending_ticket_has_no_qr_and_cannot_check_in(self):
        reservation = self._create_reservation("Pending Door", status="pending_payment_review")
        attendee = self.db.list_attendees(reservation.id)[0]

        tickets_resp = self.client.get("/api/my_tickets", params={"tg_id": self.user_tg_id})
        self.assertEqual(tickets_resp.status_code, 200, tickets_resp.text)
        ticket = tickets_resp.json()["items"][0]["tickets"][0]
        self.assertNotIn("qr_url", ticket)

        qr_resp = self.client.get(f"/api/tickets/{attendee['ticket_token']}/qr", params={"tg_id": self.user_tg_id})
        self.assertEqual(qr_resp.status_code, 403, qr_resp.text)

        checkin_resp = self.client.post(
            "/api/admin/checkin",
            json={"tg_id": self.admin_tg_id, "token": attendee["ticket_token"]},
        )
        self.assertEqual(checkin_resp.status_code, 409, checkin_resp.text)
        self.assertIn("not approved", checkin_resp.json()["detail"])

    def test_ticket_qr_requires_owner_or_admin(self):
        reservation = self._create_reservation("Private Guest", status="approved")
        attendee = self.db.list_attendees(reservation.id)[0]
        other_tg_id = 700001
        self.db.upsert_user(other_tg_id, "Other", "User", "phone")

        forbidden = self.client.get(f"/api/tickets/{attendee['ticket_token']}/qr", params={"tg_id": other_tg_id})
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        admin_allowed = self.client.get(f"/api/tickets/{attendee['ticket_token']}/qr", params={"tg_id": self.admin_tg_id})
        self.assertEqual(admin_allowed.status_code, 200, admin_allowed.text)

    def test_book_with_payment_rejects_non_image_non_pdf_upload(self):
        response = self._book_with_payment(
            filename="proof.txt",
            content=b"not allowed",
            mime="text/plain",
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("Only JPG, PNG, or PDF is accepted", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)
        self.assertEqual(len(list(Path(os.environ["UPLOAD_DIR"]).glob("*"))), 0)

    def test_book_with_payment_rejects_spoofed_image_upload(self):
        response = self._book_with_payment(
            filename="proof.png",
            content=b"not actually a png",
            mime="image/png",
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("not a valid", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)

    def test_book_with_payment_requires_terms_acceptance(self):
        response = self._book_with_payment(terms_accepted="")
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("Accept the booking terms", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)

    def test_book_with_payment_rejects_attendee_name_without_surname(self):
        response = self._book_with_payment(
            attendees=["SingleNameOnly"],
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("Name Surname", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)

    def test_book_with_payment_rejects_negative_counts_without_storing_upload(self):
        response = self._book_with_payment(
            boys=-1,
            girls=2,
            attendees=["Jane Doe"],
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("non-negative", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)
        self.assertEqual(len(list(Path(os.environ["UPLOAD_DIR"]).glob("*"))), 0)

    def test_book_with_payment_rejects_sold_out_event_without_storing_upload(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "early_qty": 0,
                "tier1_qty": 0,
                "tier2_qty": 0,
            },
        )
        response = self._book_with_payment(
            boys=1,
            girls=0,
            attendees=["John Doe"],
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("Not enough tickets", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)
        self.assertEqual(len(list(Path(os.environ["UPLOAD_DIR"]).glob("*"))), 0)

    def test_book_with_payment_requires_existing_user_profile(self):
        response = self._book_with_payment(
            tg_id=999999999,
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertIn("Create your profile before booking", response.json().get("detail", ""))

    def test_book_with_payment_rate_limit(self):
        self.server.BOOKING_RATE_LIMIT = 1
        self.db.set_event_fields(
            self.event_id,
            {
                "early_qty": 5,
                "tier1_qty": 5,
                "tier2_qty": 5,
            },
        )
        first = self._book_with_payment(attendees=["First User"])
        self.assertEqual(first.status_code, 200, first.text)

        second = self._book_with_payment(attendees=["Second User"])
        self.assertEqual(second.status_code, 429, second.text)
        self.assertIn("Too many requests", second.json().get("detail", ""))

    def test_book_with_payment_applies_repost_discount_per_attendee(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "repost_discount_enabled": 1,
                "repost_discount_amount": 1000,
            },
        )
        response = self._book_with_payment(
            boys=2,
            girls=1,
            attendees=["John Doe", "Jane Doe", "Alex Doe"],
            discounted_attendee_indexes=[0, 2],
            repost_files={
                0: ("repost-0.png", PNG_BYTES, "image/png"),
                2: ("repost-2.png", PNG_BYTES, "image/png"),
            },
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 200, response.text)

        code = response.json().get("code")
        reservation = self.db.get_reservation_by_code(code)
        self.assertIsNotNone(reservation)
        self.assertAlmostEqual(reservation.base_total_price, 7500.0)
        self.assertEqual(reservation.discount_count, 2)
        self.assertAlmostEqual(reservation.discount_unit_amount, 1000.0)
        self.assertAlmostEqual(reservation.discount_amount, 2000.0)
        self.assertAlmostEqual(reservation.total_price, 5500.0)

        attendees = self.db.list_attendees(reservation.id)
        self.assertEqual([row["repost_discount_applied"] for row in attendees], [1, 0, 1])
        self.assertTrue(attendees[0]["repost_proof_file_id"].startswith("https://example.invalid/uploads/"))
        self.assertEqual(attendees[1]["repost_proof_file_id"], "")
        self.assertTrue(attendees[2]["repost_proof_file_id"].startswith("https://example.invalid/uploads/"))

    def test_book_with_payment_applies_group_offer_discount(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "boys_group_offer_enabled": 1,
            },
        )
        response = self._book_with_payment(
            boys=4,
            girls=0,
            attendees=["John Doe", "Jane Doe", "Alex Doe", "Mark Doe"],
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 200, response.text)

        code = response.json().get("code")
        reservation = self.db.get_reservation_by_code(code)
        self.assertIsNotNone(reservation)
        self.assertAlmostEqual(reservation.base_total_price, 10000.0)
        self.assertEqual(reservation.boys_group_free_count, 1)
        self.assertEqual(reservation.girls_group_free_count, 0)
        self.assertAlmostEqual(reservation.group_discount_amount, 2500.0)
        self.assertAlmostEqual(reservation.total_price, 7500.0)

    def test_book_with_payment_uses_greater_discount_when_group_offer_and_repost_overlap(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "girls_group_offer_enabled": 1,
                "repost_discount_enabled": 1,
                "repost_discount_amount": 1000,
            },
        )
        response = self._book_with_payment(
            boys=0,
            girls=3,
            attendees=["John Doe", "Jane Doe", "Alex Doe"],
            discounted_attendee_indexes=[0, 1, 2],
            repost_files={
                0: ("repost-0.png", PNG_BYTES, "image/png"),
                1: ("repost-1.png", PNG_BYTES, "image/png"),
                2: ("repost-2.png", PNG_BYTES, "image/png"),
            },
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 200, response.text)

        code = response.json().get("code")
        reservation = self.db.get_reservation_by_code(code)
        self.assertIsNotNone(reservation)
        self.assertAlmostEqual(reservation.base_total_price, 7500.0)
        self.assertEqual(reservation.girls_group_free_count, 1)
        self.assertAlmostEqual(reservation.group_discount_amount, 2500.0)
        self.assertEqual(reservation.discount_count, 3)
        self.assertAlmostEqual(reservation.discount_amount, 3000.0)
        self.assertAlmostEqual(reservation.total_price, 4500.0)

    def test_book_with_payment_requires_repost_screenshot_for_discounted_attendee(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "repost_discount_enabled": 1,
                "repost_discount_amount": 1000,
            },
        )
        response = self._book_with_payment(
            attendees=["John Doe"],
            discounted_attendee_indexes=[0],
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("Upload repost screenshot", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)

    def test_book_with_payment_rejects_non_image_repost_upload(self):
        self.db.set_event_fields(
            self.event_id,
            {
                "repost_discount_enabled": 1,
                "repost_discount_amount": 1000,
            },
        )
        response = self._book_with_payment(
            attendees=["John Doe"],
            discounted_attendee_indexes=[0],
            repost_files={
                0: ("repost.pdf", b"%PDF-1.4", "application/pdf"),
            },
            content=PNG_BYTES,
            mime="image/png",
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("Only JPG or PNG is accepted", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)

    def test_event_payment_options_are_saved_and_visible_to_guest(self):
        create_resp = self.client.post(
            "/api/admin/event/create_simple",
            json={
                "tg_id": self.admin_tg_id,
                "title": "Payment Event",
                "caption": "Pay links",
                "early_boy": 1000,
                "early_girl": 1000,
                "early_qty": 5,
                "tier1_boy": 2000,
                "tier1_girl": 2000,
                "tier1_qty": 0,
                "tier2_boy": 3000,
                "tier2_girl": 3000,
                "tier2_qty": 0,
                "repost_discount_enabled": True,
                "repost_discount_amount": 1000,
                "girls_group_offer_enabled": True,
                "boys_group_offer_enabled": False,
                "payment1_title": "Revolut",
                "payment1_url": "https://pay.example/revolut",
                "payment2_title": "",
                "payment2_url": "https://pay.example/wise",
                "payment3_title": "Bank",
                "payment3_url": "",
            },
        )
        self.assertEqual(create_resp.status_code, 200, create_resp.text)
        event_id = create_resp.json()["event"]["id"]

        admin_events = self.client.get(
            "/api/admin/events",
            params={"tg_id": self.admin_tg_id},
        )
        self.assertEqual(admin_events.status_code, 200, admin_events.text)
        event_payload = next((x for x in admin_events.json()["items"] if x["id"] == event_id), None)
        self.assertIsNotNone(event_payload)
        payment = event_payload["payment"]
        prices = event_payload["prices"]
        self.assertEqual(payment["payment1_title"], "Revolut")
        self.assertEqual(payment["payment1_url"], "https://pay.example/revolut")
        self.assertEqual(prices["repost_discount_enabled"], 1)
        self.assertEqual(prices["repost_discount_amount"], 1000)
        self.assertEqual(prices["girls_group_offer_enabled"], 1)
        self.assertEqual(prices["boys_group_offer_enabled"], 0)

        guest_events = self.client.get("/api/events")
        self.assertEqual(guest_events.status_code, 200, guest_events.text)
        guest_payload = next((x for x in guest_events.json()["items"] if x["id"] == event_id), None)
        self.assertIsNotNone(guest_payload)
        self.assertEqual(guest_payload["repost_discount_enabled"], 1)
        self.assertEqual(guest_payload["repost_discount_amount"], 1000)
        self.assertEqual(guest_payload["girls_group_offer_enabled"], 1)
        self.assertEqual(guest_payload["boys_group_offer_enabled"], 0)
        option_urls = [opt["url"] for opt in guest_payload.get("payment_options", [])]
        self.assertIn("https://pay.example/revolut", option_urls)
        self.assertIn("https://pay.example/wise", option_urls)
        self.assertNotIn("", option_urls)

    def test_event_repost_discount_fields_can_be_updated_via_admin_api(self):
        update_resp = self.client.post(
            "/api/admin/event/update",
            json={
                "tg_id": self.admin_tg_id,
                "event_id": self.event_id,
                "updates": {
                    "repost_discount_enabled": True,
                    "repost_discount_amount": 1750,
                    "girls_group_offer_enabled": True,
                    "boys_group_offer_enabled": False,
                },
            },
        )
        self.assertEqual(update_resp.status_code, 200, update_resp.text)
        event = self.db.get_event(self.event_id)
        self.assertEqual(event.repost_discount_enabled, 1)
        self.assertEqual(event.repost_discount_amount, 1750.0)
        self.assertEqual(event.girls_group_offer_enabled, 1)
        self.assertEqual(event.boys_group_offer_enabled, 0)

        admin_events = self.client.get(
            "/api/admin/events",
            params={"tg_id": self.admin_tg_id},
        )
        self.assertEqual(admin_events.status_code, 200, admin_events.text)
        event_payload = next((x for x in admin_events.json()["items"] if x["id"] == self.event_id), None)
        self.assertIsNotNone(event_payload)
        self.assertEqual(event_payload["prices"]["repost_discount_enabled"], 1)
        self.assertEqual(event_payload["prices"]["repost_discount_amount"], 1750.0)
        self.assertEqual(event_payload["prices"]["girls_group_offer_enabled"], 1)
        self.assertEqual(event_payload["prices"]["boys_group_offer_enabled"], 0)

    def test_event_payment_url_requires_https(self):
        bad_create = self.client.post(
            "/api/admin/event/create_simple",
            json={
                "tg_id": self.admin_tg_id,
                "title": "Bad Payment",
                "caption": "Bad URL",
                "early_boy": 1000,
                "early_girl": 1000,
                "early_qty": 5,
                "tier1_boy": 2000,
                "tier1_girl": 2000,
                "tier1_qty": 0,
                "tier2_boy": 3000,
                "tier2_girl": 3000,
                "tier2_qty": 0,
                "payment1_title": "Bad",
                "payment1_url": "http://not-secure.example",
            },
        )
        self.assertEqual(bad_create.status_code, 400, bad_create.text)
        self.assertIn("https://", bad_create.json().get("detail", ""))

        bad_update = self.client.post(
            "/api/admin/event/update",
            json={
                "tg_id": self.admin_tg_id,
                "event_id": self.event_id,
                "updates": {"payment1_url": "http://not-secure.example"},
            },
        )
        self.assertEqual(bad_update.status_code, 400, bad_update.text)
        self.assertIn("https://", bad_update.json().get("detail", ""))

    def test_cleanup_upload_storage_removes_orphan_and_old_reviewed_keeps_pending(self):
        upload_dir = os.environ["UPLOAD_DIR"]
        os.makedirs(upload_dir, exist_ok=True)
        self.db.set_event_fields(
            self.event_id,
            {
                "repost_discount_enabled": 1,
                "repost_discount_amount": 1000,
            },
        )

        pending_path = os.path.join(upload_dir, "pending.jpg")
        reviewed_path = os.path.join(upload_dir, "reviewed.jpg")
        repost_pending_path = os.path.join(upload_dir, "repost-pending.jpg")
        repost_reviewed_path = os.path.join(upload_dir, "repost-reviewed.jpg")
        orphan_path = os.path.join(upload_dir, "orphan.jpg")

        for file_path in (pending_path, reviewed_path, repost_pending_path, repost_reviewed_path, orphan_path):
            with open(file_path, "wb") as fh:
                fh.write(b"test")

        pending_res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=["Pending User"],
            payment_file_id="/uploads/pending.jpg",
            payment_file_type="external",
            discounted_attendee_indexes=[0],
            repost_proofs_by_index={0: ("/uploads/repost-pending.jpg", "external")},
        )
        reviewed_res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=["Reviewed User"],
            payment_file_id="/uploads/reviewed.jpg",
            payment_file_type="external",
            discounted_attendee_indexes=[0],
            repost_proofs_by_index={0: ("/uploads/repost-reviewed.jpg", "external")},
        )
        ok, _msg, _approved = self.db.approve_reservation(reviewed_res.id, self.admin_tg_id)
        self.assertTrue(ok)

        old_ts = time.time() - (8 * 24 * 60 * 60)
        for file_path in (pending_path, reviewed_path, repost_pending_path, repost_reviewed_path, orphan_path):
            os.utime(file_path, (old_ts, old_ts))

        report = self.server.cleanup_upload_storage(now_ts=time.time())
        self.assertGreaterEqual(report.get("deleted", 0), 3)

        self.assertTrue(os.path.exists(pending_path), "Pending proof should not be deleted.")
        self.assertTrue(os.path.exists(repost_pending_path), "Pending repost proof should not be deleted.")
        self.assertFalse(os.path.exists(reviewed_path), "Old reviewed proof should be deleted.")
        self.assertFalse(os.path.exists(repost_reviewed_path), "Old reviewed repost proof should be deleted.")
        self.assertFalse(os.path.exists(orphan_path), "Orphan file should be deleted.")
        self.assertIsNotNone(pending_res)

    def test_blocked_web_user_is_forbidden_on_me_and_booking(self):
        # Create a website (email-login) user and establish a web session cookie.
        start_resp = self.client.post(
            "/api/web/login/start",
            json={
                "name": "Blocked",
                "surname": "Guest",
                "email": "blocked.guest@example.invalid",
                "phone": "+36 20 555 0000",
            },
        )
        self.assertEqual(start_resp.status_code, 200, start_resp.text)
        verify_resp = self.client.post(
            "/api/web/login/verify",
            json={"email": "blocked.guest@example.invalid", "code": start_resp.json()["dev_code"]},
        )
        self.assertEqual(verify_resp.status_code, 200, verify_resp.text)

        # Sanity: the freshly registered user can access /api/me before being blocked.
        ok_me = self.client.get("/api/me")
        self.assertEqual(ok_me.status_code, 200, ok_me.text)

        # Block the user directly in the database.
        self.db.conn.execute(
            "UPDATE users SET blocked = 1 WHERE email = ?",
            ("blocked.guest@example.invalid",),
        )
        self.db.conn.commit()

        # /api/me must now be forbidden.
        me_resp = self.client.get("/api/me")
        self.assertEqual(me_resp.status_code, 403, me_resp.text)
        self.assertIn("blocked", me_resp.json()["detail"].lower())

        # Booking must also be blocked (it flows through _request_user).
        booking_resp = self.client.post(
            "/api/book_with_payment",
            data={
                "event_id": str(self.event_id),
                "boys": "1",
                "girls": "0",
                "attendees": json.dumps(["Blocked Guest"]),
                "discounted_attendee_indexes": "[]",
                "terms_accepted": "true",
            },
            files=[("file", ("proof.png", PNG_BYTES, "image/png"))],
        )
        self.assertEqual(booking_resp.status_code, 403, booking_resp.text)
        self.assertIn("blocked", booking_resp.json()["detail"].lower())

    def test_blocked_telegram_user_is_forbidden_on_me_and_booking(self):
        # QA gap coverage: verify the Telegram (tg_id) path of _request_user also
        # enforces the block, not just the web-session path.
        ok_me = self.client.get("/api/me", params={"tg_id": self.user_tg_id})
        self.assertEqual(ok_me.status_code, 200, ok_me.text)

        # Block the Telegram user directly in the database.
        self.db.conn.execute(
            "UPDATE users SET blocked = 1 WHERE tg_id = ?",
            (self.user_tg_id,),
        )
        self.db.conn.commit()

        # /api/me must now be forbidden for the blocked Telegram user.
        me_resp = self.client.get("/api/me", params={"tg_id": self.user_tg_id})
        self.assertEqual(me_resp.status_code, 403, me_resp.text)
        self.assertIn("blocked", me_resp.json()["detail"].lower())

        # Booking (flows through _request_user) must also be blocked.
        booking_resp = self._book_with_payment(tg_id=self.user_tg_id, attendees=["Blocked Guest"])
        self.assertEqual(booking_resp.status_code, 403, booking_resp.text)
        self.assertIn("blocked", booking_resp.json()["detail"].lower())

        # A different, non-blocked Telegram user still works (no over-blocking).
        other_tg_id = 424242424
        self.db.upsert_user(other_tg_id, "Other", "User", "phone")
        other_me = self.client.get("/api/me", params={"tg_id": other_tg_id})
        self.assertEqual(other_me.status_code, 200, other_me.text)


if __name__ == "__main__":
    unittest.main()
