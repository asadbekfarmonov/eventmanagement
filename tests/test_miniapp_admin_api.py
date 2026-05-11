import json
import importlib
import os
import tempfile
import time
import unittest
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from openpyxl import Workbook


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
            "WEB_APP_URL",
            "UPLOAD_DIR",
            "UPLOAD_MAX_MB",
            "UPLOAD_RETENTION_DAYS",
            "UPLOAD_CLEANUP_INTERVAL_SECONDS",
        )
        self._env_backup = {key: os.environ.get(key) for key in self._env_keys}
        os.environ["DATABASE_PATH"] = self.db_path
        os.environ["ADMIN_IDS"] = str(self.admin_tg_id)
        os.environ["BOT_TOKEN"] = ""
        os.environ["WEB_APP_URL"] = "https://example.invalid"
        os.environ["UPLOAD_DIR"] = os.path.join(self.temp_dir.name, "uploads")
        os.environ["UPLOAD_MAX_MB"] = "5"
        os.environ["UPLOAD_RETENTION_DAYS"] = "7"
        os.environ["UPLOAD_CLEANUP_INTERVAL_SECONDS"] = "3600"

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
        content=b"image-bytes",
        mime="image/png",
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
            },
            files=files,
        )

    def test_logo_static_file_is_served(self):
        response = self.client.get("/static/logo.png")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("content-type", "").startswith("image/png"))
        self.assertGreater(len(response.content), 1000)

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
            content=b"fake-png",
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

    def test_book_with_payment_rejects_non_image_non_pdf_upload(self):
        response = self._book_with_payment(
            filename="proof.txt",
            content=b"not allowed",
            mime="text/plain",
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("Only image or PDF is accepted", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)
        self.assertEqual(len(list(Path(os.environ["UPLOAD_DIR"]).glob("*"))), 0)

    def test_book_with_payment_rejects_attendee_name_without_surname(self):
        response = self._book_with_payment(
            attendees=["SingleNameOnly"],
            content=b"fake-png",
            mime="image/png",
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("Name Surname", response.json().get("detail", ""))
        reservation_count = self.db.conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(reservation_count, 0)

    def test_book_with_payment_requires_existing_user_profile(self):
        response = self._book_with_payment(
            tg_id=999999999,
            content=b"fake-png",
            mime="image/png",
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertIn("Run /start in bot", response.json().get("detail", ""))

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
                0: ("repost-0.png", b"repost-zero", "image/png"),
                2: ("repost-2.jpg", b"repost-two", "image/jpeg"),
            },
            content=b"payment-proof",
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
            content=b"payment-proof",
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
            content=b"payment-proof",
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
            content=b"payment-proof",
            mime="image/png",
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("Only image is accepted", response.json().get("detail", ""))
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


if __name__ == "__main__":
    unittest.main()
