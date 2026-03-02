import importlib
import os
import tempfile
import time
import unittest
from io import BytesIO

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
        return reservation

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

    def test_cleanup_upload_storage_removes_orphan_and_old_reviewed_keeps_pending(self):
        upload_dir = os.environ["UPLOAD_DIR"]
        os.makedirs(upload_dir, exist_ok=True)

        pending_path = os.path.join(upload_dir, "pending.jpg")
        reviewed_path = os.path.join(upload_dir, "reviewed.jpg")
        orphan_path = os.path.join(upload_dir, "orphan.jpg")

        for file_path in (pending_path, reviewed_path, orphan_path):
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
        )
        reviewed_res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=["Reviewed User"],
            payment_file_id="/uploads/reviewed.jpg",
            payment_file_type="external",
        )
        ok, _msg, _approved = self.db.approve_reservation(reviewed_res.id, self.admin_tg_id)
        self.assertTrue(ok)

        old_ts = time.time() - (8 * 24 * 60 * 60)
        for file_path in (pending_path, reviewed_path, orphan_path):
            os.utime(file_path, (old_ts, old_ts))

        report = self.server.cleanup_upload_storage(now_ts=time.time())
        self.assertGreaterEqual(report.get("deleted", 0), 2)

        self.assertTrue(os.path.exists(pending_path), "Pending proof should not be deleted.")
        self.assertFalse(os.path.exists(reviewed_path), "Old reviewed proof should be deleted.")
        self.assertFalse(os.path.exists(orphan_path), "Orphan file should be deleted.")
        self.assertIsNotNone(pending_res)


if __name__ == "__main__":
    unittest.main()
