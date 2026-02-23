import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ticketbot.database import (
    STATUS_APPROVED,
    STATUS_CANCELLED,
    STATUS_PENDING,
    STATUS_REJECTED,
    Database,
)

BUDAPEST_TZ = ZoneInfo("Europe/Budapest")


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db = Database(self.db_path)

        self.db.upsert_user(123, "Test", "User", "12345")
        user = self.db.get_user(123)
        self.user_id = user.id

    def tearDown(self):
        self.temp_dir.cleanup()

    def _future_time_str(self, hours_from_now: int) -> str:
        local_dt = datetime.now(timezone.utc).astimezone(BUDAPEST_TZ) + timedelta(hours=hours_from_now)
        return local_dt.strftime("%Y-%m-%d %H:%M")

    def _create_event(self, early_qty=5, t1_qty=5, t2_qty=5):
        return self.db.create_event(
            title="Sample Event",
            event_datetime=self._future_time_str(120),
            location="Sample Hall",
            caption="Sample caption",
            photo_file_id="photo-file-id",
            early_boy_price=2500.0,
            early_girl_price=2600.0,
            early_qty=early_qty,
            tier1_boy_price=3500.0,
            tier1_girl_price=3600.0,
            tier1_qty=t1_qty,
            tier2_boy_price=4500.0,
            tier2_girl_price=4600.0,
            tier2_qty=t2_qty,
        )

    def test_pending_reservation_uses_gender_prices_and_holds_stock(self):
        event_id = self._create_event(early_qty=10, t1_qty=0, t2_qty=0)

        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=2,
            girls=1,
            attendees=["A One", "B Two", "C Three"],
            payment_file_id="proof-file",
            payment_file_type="document",
        )

        self.assertEqual(reservation.status, STATUS_PENDING)
        self.assertEqual(reservation.quantity, 3)
        self.assertEqual(reservation.total_price, 7600.0)

        event = self.db.get_event(event_id)
        self.assertEqual(event.early_bird_qty, 7)

    def test_pending_hold_moves_active_tier(self):
        event_id = self._create_event(early_qty=1, t1_qty=2, t2_qty=0)

        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=1,
            girls=0,
            attendees=["A One"],
            payment_file_id="proof",
            payment_file_type="photo",
        )
        self.assertEqual(reservation.ticket_type, "early")

        event_after = self.db.get_event(event_id)
        active_tier = self.db.active_tier(event_after)
        self.assertEqual(active_tier["key"], "tier1")

    def test_reject_releases_hold(self):
        event_id = self._create_event(early_qty=3, t1_qty=0, t2_qty=0)

        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=1,
            girls=1,
            attendees=["A One", "B Two"],
            payment_file_id="proof",
            payment_file_type="photo",
        )

        ok, _msg, updated = self.db.reject_reservation(
            reservation_id=reservation.id,
            admin_tg_id=999,
            admin_note="Wrong amount",
        )
        self.assertTrue(ok)
        self.assertEqual(updated.status, STATUS_REJECTED)

        event_after = self.db.get_event(event_id)
        self.assertEqual(event_after.early_bird_qty, 3)

    def test_cancel_allowed_anytime_and_releases_hold(self):
        event_id = self._create_event(early_qty=4, t1_qty=0, t2_qty=0)
        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=2,
            girls=0,
            attendees=["A One", "B Two"],
            payment_file_id="proof",
            payment_file_type="photo",
        )

        ok, _msg, cancelled = self.db.cancel_reservation_for_user(self.user_id, reservation.code)
        self.assertTrue(ok)
        self.assertEqual(cancelled.status, STATUS_CANCELLED)

        event_after = self.db.get_event(event_id)
        self.assertEqual(event_after.early_bird_qty, 4)

    def test_event_stats_aggregates_counts_and_values(self):
        event_id = self._create_event(early_qty=12, t1_qty=0, t2_qty=0)

        approved_res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=2,
            girls=0,
            attendees=["A One", "B Two"],
            payment_file_id="proof-a",
            payment_file_type="photo",
        )
        self.db.approve_reservation(approved_res.id, admin_tg_id=700)

        rejected_res = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=1,
            girls=0,
            attendees=["C Three"],
            payment_file_id="proof-b",
            payment_file_type="photo",
        )
        self.db.reject_reservation(rejected_res.id, admin_tg_id=700, admin_note="invalid")

        self.db.upsert_user(456, "Second", "User", "67890")
        second_user = self.db.get_user(456)
        self.db.create_pending_reservation(
            user_id=second_user.id,
            event_id=event_id,
            boys=0,
            girls=1,
            attendees=["D Four"],
            payment_file_id="proof-c",
            payment_file_type="document",
        )

        rows = self.db.list_event_stats(sort_by="approved")
        row = next(r for r in rows if r["id"] == event_id)
        self.assertEqual(row["approved_tickets"], 2)
        self.assertEqual(row["pending_tickets"], 1)
        self.assertEqual(row["rejected_tickets"], 1)
        self.assertEqual(row["cancelled_tickets"], 0)
        self.assertEqual(row["held_tickets"], 3)
        self.assertAlmostEqual(float(row["approved_revenue"]), 5000.0)
        self.assertAlmostEqual(float(row["pending_revenue"]), 2600.0)

    def test_search_reservations_matches_code_event_and_buyer(self):
        event_id = self._create_event(early_qty=6, t1_qty=0, t2_qty=0)
        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=1,
            girls=0,
            attendees=["Find Me"],
            payment_file_id="proof",
            payment_file_type="photo",
        )

        by_event = self.db.search_reservations("sample event", sort_by="newest", limit=10)
        self.assertTrue(any(r["code"] == reservation.code for r in by_event))

        by_code = self.db.search_reservations(reservation.code[-4:], sort_by="amount", limit=10)
        self.assertTrue(any(r["code"] == reservation.code for r in by_code))

        by_name = self.db.search_reservations("test", sort_by="status", limit=10)
        self.assertTrue(any(r["code"] == reservation.code for r in by_name))

    def test_admin_guest_add_remove_rename_and_list(self):
        event_id = self._create_event(early_qty=5, t1_qty=0, t2_qty=0)
        reservation = self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=1,
            girls=1,
            attendees=["A One", "B Two"],
            payment_file_id="proof",
            payment_file_type="photo",
        )

        ok_add, _msg_add, updated_after_add = self.db.admin_add_guest(
            reservation_code=reservation.code,
            full_name="C Three",
            gender_raw="boy",
        )
        self.assertTrue(ok_add)
        self.assertEqual(updated_after_add.quantity, 3)
        self.assertEqual(updated_after_add.boys, 2)
        self.assertEqual(updated_after_add.girls, 1)
        self.assertAlmostEqual(updated_after_add.total_price, 7600.0)

        event_after_add = self.db.get_event(event_id)
        self.assertEqual(event_after_add.early_bird_qty, 2)

        guests = self.db.list_guests(sort_by="newest", search=reservation.code, limit=10)
        self.assertTrue(any(g["reservation_code"] == reservation.code for g in guests))

        newest_attendee_id = guests[0]["attendee_id"]
        ok_rename, _msg_rename = self.db.admin_rename_guest(newest_attendee_id, "Renamed Guest")
        self.assertTrue(ok_rename)

        ok_remove, _msg_remove, updated_after_remove = self.db.admin_remove_guest(newest_attendee_id)
        self.assertTrue(ok_remove)
        self.assertEqual(updated_after_remove.quantity, 2)
        self.assertEqual(updated_after_remove.boys, 1)
        self.assertEqual(updated_after_remove.girls, 1)
        self.assertAlmostEqual(updated_after_remove.total_price, 5100.0)

        event_after_remove = self.db.get_event(event_id)
        self.assertEqual(event_after_remove.early_bird_qty, 3)

    def test_set_event_fields_updates_info_and_prices(self):
        event_id = self._create_event(early_qty=5, t1_qty=2, t2_qty=1)
        new_dt = self._future_time_str(180)
        ok, message = self.db.set_event_fields(
            event_id,
            {
                "caption": "Updated caption text",
                "location": "Updated location",
                "early_boy": "2700",
                "tier1_qty": "9",
                "datetime": new_dt,
            },
        )
        self.assertTrue(ok, msg=message)

        event = self.db.get_event(event_id)
        self.assertEqual(event.caption, "Updated caption text")
        self.assertEqual(event.location, "Updated location")
        self.assertEqual(event.early_bird_price, 2700.0)
        self.assertEqual(event.regular_tier1_qty, 9)
        self.assertEqual(event.event_datetime, new_dt)

    def test_admin_add_guest_by_event_and_remove_by_name(self):
        event_id = self._create_event(early_qty=2, t1_qty=0, t2_qty=0)

        ok_add, _msg_add, reservation = self.db.admin_add_guest_by_event(
            admin_tg_id=7164876915,
            event_id=event_id,
            name="Olzhas",
            surname="Olzhasov",
            gender_raw="boy",
        )
        self.assertTrue(ok_add)
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.status, STATUS_APPROVED)
        self.assertEqual(reservation.quantity, 1)
        self.assertEqual(reservation.boys, 1)
        self.assertEqual(reservation.girls, 0)

        event_after_add = self.db.get_event(event_id)
        self.assertEqual(event_after_add.early_bird_qty, 1)

        ok_remove, _msg_remove, updated_res = self.db.admin_remove_guest_by_name(
            event_id=event_id,
            name="Olzhas",
            surname="Olzhasov",
        )
        self.assertTrue(ok_remove)
        self.assertIsNotNone(updated_res)
        self.assertEqual(updated_res.status, STATUS_CANCELLED)
        self.assertEqual(updated_res.quantity, 0)

        event_after_remove = self.db.get_event(event_id)
        self.assertEqual(event_after_remove.early_bird_qty, 2)

    def test_list_guest_name_pairs_splits_legacy_full_name(self):
        event_id = self._create_event(early_qty=3, t1_qty=0, t2_qty=0)
        self.db.create_pending_reservation(
            user_id=self.user_id,
            event_id=event_id,
            boys=1,
            girls=0,
            attendees=["Olzhas Olzhasov"],
            payment_file_id="proof",
            payment_file_type="photo",
        )
        pairs = self.db.list_guest_name_pairs()
        self.assertTrue(("Olzhas", "Olzhasov") in pairs)

    def test_migrates_legacy_schema_for_new_fields(self):
        legacy_path = os.path.join(self.temp_dir.name, "legacy.db")
        conn = sqlite3.connect(legacy_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_datetime TEXT NOT NULL,
                location TEXT NOT NULL,
                early_bird_price REAL NOT NULL,
                regular_price REAL NOT NULL,
                early_bird_qty INTEGER NOT NULL,
                capacity INTEGER,
                status TEXT NOT NULL DEFAULT 'open'
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                ticket_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price_per_ticket REAL NOT NULL,
                total_price REAL NOT NULL,
                boys INTEGER NOT NULL,
                girls INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'reserved',
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE attendees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'reserved'
            )
            """
        )
        conn.commit()
        conn.close()

        migrated_db = Database(legacy_path)
        event_cols = migrated_db._table_columns("events")
        reservation_cols = migrated_db._table_columns("reservations")
        attendee_cols = migrated_db._table_columns("attendees")

        self.assertIn("early_bird_price_girl", event_cols)
        self.assertIn("regular_tier1_price_girl", event_cols)
        self.assertIn("payment_file_id", reservation_cols)
        self.assertIn("admin_note", reservation_cols)
        self.assertIn("hold_applied", reservation_cols)
        self.assertIn("full_name", attendee_cols)
        self.assertIn("gender", attendee_cols)

        migrated_db.upsert_user(777, "Legacy", "User", "000")
        legacy_user = migrated_db.get_user(777)
        migrated_event_id = migrated_db.create_event(
            title="Legacy Event",
            event_datetime=self._future_time_str(120),
            location="Legacy Hall",
            caption="Legacy caption",
            photo_file_id="legacy-photo",
            early_boy_price=1000.0,
            early_girl_price=1000.0,
            early_qty=10,
            tier1_boy_price=2000.0,
            tier1_girl_price=2000.0,
            tier1_qty=0,
            tier2_boy_price=3000.0,
            tier2_girl_price=3000.0,
            tier2_qty=0,
        )
        migrated_reservation = migrated_db.create_pending_reservation(
            user_id=legacy_user.id,
            event_id=migrated_event_id,
            boys=1,
            girls=0,
            attendees=["Legacy User"],
            payment_file_id="legacy-proof",
            payment_file_type="document",
        )
        self.assertEqual(migrated_reservation.status, STATUS_PENDING)


if __name__ == "__main__":
    unittest.main()
