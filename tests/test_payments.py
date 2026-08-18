"""Tests for payment-option selection on bookings and the admin money-by-option report.

Covers feature (2): buyers choose which payment option they used when the event has
options; the choice is stored on the reservation (``payment_slot``) and an admin
report sums APPROVED bookings per option.
"""

import importlib
import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02"
    b"\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f\x00\x02\xeb"
    b"\x01\xf6\xc5\xbb\xc7\x00\x00\x00\x00IEND\xaeB`\x82"
)


class PaymentSlotMigrationTests(unittest.TestCase):
    """The ``payment_slot`` column is created on fresh DBs and back-filled on old ones."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "migrate.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _columns(self, db):
        return [row[1] for row in db.conn.execute("PRAGMA table_info(reservations)").fetchall()]

    def test_fresh_schema_has_payment_slot_defaulting_to_zero(self):
        from ticketbot.database import Database

        db = Database(self.db_path)
        try:
            self.assertIn("payment_slot", self._columns(db))
        finally:
            db.conn.close()

    def test_migration_backfills_missing_payment_slot_column(self):
        from ticketbot.database import Database

        db = Database(self.db_path)
        try:
            # Simulate a pre-feature database that predates the payment_slot column.
            db.conn.execute("ALTER TABLE reservations DROP COLUMN payment_slot")
            db.conn.commit()
            self.assertNotIn("payment_slot", self._columns(db))

            # Re-running the migration must add the column back with a 0 default.
            db._migrate_schema()
            self.assertIn("payment_slot", self._columns(db))
        finally:
            db.conn.close()


class PaymentOptionsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "payments_test.db")
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
        os.environ["BOOKING_RATE_LIMIT"] = "50"
        os.environ["ADMIN_WEB_PASSWORD"] = "test-admin-password"
        os.environ["EMAIL_LOGIN_DEV_MODE"] = "1"
        os.environ["GOOGLE_CLIENT_ID"] = ""

        import ticketbot.miniapp_server as miniapp_server

        self.server = importlib.reload(miniapp_server)
        self.client = TestClient(self.server.app)
        self.db = self.server.db

        self.db.upsert_user(self.user_tg_id, "Buyer", "User", "phone")
        self.user_id = self.db.get_user(self.user_tg_id).id
        # Base event WITHOUT payment options.
        self.event_id = self._create_event()
        # Event WITH two payment options (slots 1 and 2 have a URL; slot 3 does not).
        self.opt_event_id = self._create_event()
        self._set_options(
            self.opt_event_id,
            {
                "payment1_title": "Revolut",
                "payment1_url": "https://pay.example/revolut",
                "payment2_title": "",  # title omitted -> defaults to "Payment Option 2"
                "payment2_url": "https://pay.example/wise",
            },
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

    # ---- helpers -------------------------------------------------------
    def _create_event(self) -> int:
        return self.db.create_event(
            title="Payment Event",
            event_datetime="2026-04-04 20:00",
            location="Budapest",
            caption="Caption",
            photo_file_id="",
            early_boy_price=2000.0,
            early_girl_price=2000.0,
            early_qty=50,
            tier1_boy_price=3000.0,
            tier1_girl_price=3000.0,
            tier1_qty=0,
            tier2_boy_price=4000.0,
            tier2_girl_price=4000.0,
            tier2_qty=0,
        )

    def _set_options(self, event_id: int, updates: dict) -> None:
        resp = self.client.post(
            "/api/admin/event/update",
            json={"tg_id": self.admin_tg_id, "event_id": event_id, "updates": updates},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

    def _book(self, event_id, *, payment_slot=None, name="Test Guest", boys=1, girls=0):
        data = {
            "tg_id": str(self.user_tg_id),
            "event_id": str(event_id),
            "boys": str(boys),
            "girls": str(girls),
            "attendees": json.dumps([name]),
            "discounted_attendee_indexes": "[]",
            "terms_accepted": "true",
        }
        if payment_slot is not None:
            data["payment_slot"] = str(payment_slot)
        return self.client.post(
            "/api/book_with_payment",
            data=data,
            files=[("file", ("proof.png", PNG_BYTES, "image/png"))],
        )

    def _make_reservation(self, event_id, payment_slot, status="pending_payment_review"):
        res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=1,
            girls=0,
            attendees=["Slot Guest"],
            payment_file_id="proof",
            payment_file_type="photo",
            payment_slot=payment_slot,
        )
        if status == "approved":
            ok, _msg, approved = self.db.approve_reservation(res.id, self.admin_tg_id)
            self.assertTrue(ok, _msg)
            return self.db.get_reservation(res.id)
        return res

    # ---- database layer -----------------------------------------------
    def test_create_pending_reservation_stores_payment_slot(self):
        res = self._make_reservation(self.opt_event_id, payment_slot=2)
        stored = self.db.get_reservation(res.id)
        self.assertEqual(stored.payment_slot, 2)

    def test_create_pending_reservation_defaults_slot_zero(self):
        res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=self.event_id,
            boys=1,
            girls=0,
            attendees=["No Slot"],
            payment_file_id="proof",
            payment_file_type="photo",
        )
        self.assertEqual(self.db.get_reservation(res.id).payment_slot, 0)

    def test_payment_option_totals_counts_only_approved_per_slot(self):
        a = self._make_reservation(self.opt_event_id, 1, status="approved")
        b = self._make_reservation(self.opt_event_id, 1, status="approved")
        c = self._make_reservation(self.opt_event_id, 1, status="pending_payment_review")
        d = self._make_reservation(self.opt_event_id, 2, status="approved")
        e = self._make_reservation(self.opt_event_id, 2, status="pending_payment_review")

        totals = {row["slot"]: row for row in self.db.payment_option_totals(self.opt_event_id)}

        self.assertEqual(totals[1]["approved_count"], 2)
        self.assertAlmostEqual(totals[1]["approved_total"], a.total_price + b.total_price)
        self.assertEqual(totals[1]["pending_count"], 1)
        self.assertAlmostEqual(totals[1]["pending_total"], c.total_price)

        self.assertEqual(totals[2]["approved_count"], 1)
        self.assertAlmostEqual(totals[2]["approved_total"], d.total_price)
        self.assertEqual(totals[2]["pending_count"], 1)
        self.assertAlmostEqual(totals[2]["pending_total"], e.total_price)

        # Slot 3 is unused -> all zeros.
        self.assertEqual(totals[3]["approved_count"], 0)
        self.assertEqual(totals[3]["approved_total"], 0.0)
        self.assertEqual(totals[3]["pending_count"], 0)

    def test_payment_option_totals_ignores_slot_zero_bookings(self):
        # A slot-0 booking on the option event must never leak into any slot total.
        self._make_reservation(self.opt_event_id, 0, status="approved")
        totals = self.db.payment_option_totals(self.opt_event_id)
        for row in totals:
            self.assertEqual(row["approved_count"], 0)
            self.assertEqual(row["approved_total"], 0.0)

    # ---- booking endpoint ---------------------------------------------
    def test_book_stores_chosen_slot_when_event_has_options(self):
        resp = self._book(self.opt_event_id, payment_slot=1, name="Chose One")
        self.assertEqual(resp.status_code, 200, resp.text)
        res = self.db.get_reservation_by_code(resp.json()["code"])
        self.assertEqual(res.payment_slot, 1)

    def test_book_rejects_missing_slot_when_event_has_options(self):
        resp = self._book(self.opt_event_id, payment_slot=None, name="No Choice")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("payment option", resp.text.lower())

    def test_book_rejects_invalid_slot_without_url(self):
        # Slot 3 has no configured URL, so it is not a selectable option.
        resp = self._book(self.opt_event_id, payment_slot=3, name="Bad Slot")
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_book_rejects_non_integer_slot(self):
        resp = self._book(self.opt_event_id, payment_slot="abc", name="NaN Slot")
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_book_allows_slot_zero_when_no_options(self):
        resp = self._book(self.event_id, payment_slot=None, name="Optionless Buyer")
        self.assertEqual(resp.status_code, 200, resp.text)
        res = self.db.get_reservation_by_code(resp.json()["code"])
        self.assertEqual(res.payment_slot, 0)

    def test_book_forces_slot_zero_when_no_options_even_if_slot_sent(self):
        resp = self._book(self.event_id, payment_slot=1, name="Ignored Slot")
        self.assertEqual(resp.status_code, 200, resp.text)
        res = self.db.get_reservation_by_code(resp.json()["code"])
        self.assertEqual(res.payment_slot, 0)

    # ---- admin totals endpoint ----------------------------------------
    def test_admin_totals_requires_authentication(self):
        resp = self.client.get("/api/admin/payment/totals", params={"event_id": self.opt_event_id})
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_admin_totals_forbidden_for_non_admin(self):
        resp = self.client.get(
            "/api/admin/payment/totals",
            params={"event_id": self.opt_event_id, "tg_id": self.user_tg_id},
        )
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_admin_totals_pairs_titles_and_ignores_slot_zero(self):
        a = self._make_reservation(self.opt_event_id, 1, status="approved")
        self._make_reservation(self.opt_event_id, 1, status="pending_payment_review")
        # A slot-0 approved booking must not appear in the report.
        self._make_reservation(self.opt_event_id, 0, status="approved")

        resp = self.client.get(
            "/api/admin/payment/totals",
            params={"event_id": self.opt_event_id, "tg_id": self.admin_tg_id},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["event_id"], self.opt_event_id)
        items = {item["slot"]: item for item in body["items"]}

        # Only configured options (slots 1 and 2) are reported; slot 3 is excluded.
        self.assertEqual(set(items.keys()), {1, 2})
        self.assertEqual(items[1]["title"], "Revolut")
        self.assertEqual(items[2]["title"], "Payment Option 2")  # default label when title blank
        self.assertEqual(items[1]["approved_count"], 1)
        self.assertAlmostEqual(items[1]["approved_total"], a.total_price)
        self.assertEqual(items[1]["pending_count"], 1)
        self.assertEqual(items[2]["approved_count"], 0)

    def test_admin_totals_empty_for_event_without_options(self):
        resp = self.client.get(
            "/api/admin/payment/totals",
            params={"event_id": self.event_id, "tg_id": self.admin_tg_id},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["items"], [])

    def test_admin_totals_404_for_unknown_event(self):
        resp = self.client.get(
            "/api/admin/payment/totals",
            params={"event_id": 999999, "tg_id": self.admin_tg_id},
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    # ---- admin-created / imported guests default to slot 0 ------------
    def test_admin_add_guest_by_event_defaults_slot_zero_even_with_options(self):
        ok, msg, res = self.db.admin_add_guest_by_event(
            admin_tg_id=self.admin_tg_id,
            event_id=self.opt_event_id,  # event HAS payment options
            name="Walk",
            surname="In",
            gender_raw="boy",
        )
        self.assertTrue(ok, msg)
        self.assertEqual(self.db.get_reservation(res.id).payment_slot, 0)

    def test_admin_import_guest_by_event_defaults_slot_zero_even_with_options(self):
        ok, msg, res = self.db.admin_import_guest_by_event(
            admin_tg_id=self.admin_tg_id,
            event_id=self.opt_event_id,  # event HAS payment options
            name="Imported",
            surname="Guest",
        )
        self.assertTrue(ok, msg)
        self.assertEqual(self.db.get_reservation(res.id).payment_slot, 0)

    # ---- slot surfaced in my_tickets and pending review ---------------
    def test_my_tickets_includes_payment_slot_and_title(self):
        resp = self._book(self.opt_event_id, payment_slot=2, name="Ticket Owner")
        self.assertEqual(resp.status_code, 200, resp.text)

        tickets = self.client.get("/api/my_tickets", params={"tg_id": self.user_tg_id})
        self.assertEqual(tickets.status_code, 200, tickets.text)
        item = tickets.json()["items"][0]
        self.assertEqual(item["payment_slot"], 2)
        self.assertEqual(item["payment_slot_title"], "Payment Option 2")

    def test_pending_review_includes_payment_slot_and_title(self):
        self._book(self.opt_event_id, payment_slot=1, name="Pending Owner")

        pending = self.client.get(
            "/api/admin/reservation/pending", params={"tg_id": self.admin_tg_id}
        )
        self.assertEqual(pending.status_code, 200, pending.text)
        items = pending.json()["items"]
        self.assertTrue(items)
        item = items[0]
        self.assertEqual(item["payment_slot"], 1)
        self.assertEqual(item["payment_slot_title"], "Revolut")


if __name__ == "__main__":
    unittest.main()
