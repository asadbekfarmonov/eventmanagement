import os
import tempfile
import unittest

from ticketbot.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db = Database(self.db_path)
        self.user_id = self._seed_user()
        self.event_id = self._seed_event()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed_user(self):
        self.db.upsert_user(123, "Test", "User", "12345")
        user = self.db.get_user(123)
        return user.id

    def _seed_event(self):
        return self.db.create_event(
            title="Sample Event",
            event_datetime="2024-01-01 18:00",
            location="Sample Hall",
            early_bird_price=10.0,
            regular_price=20.0,
            early_bird_qty=5,
            capacity=None,
        )

    def test_reservation_decrements_early_bird(self):
        reservation = self.db.reserve_event(
            user_id=self.user_id,
            event_id=self.event_id,
            ticket_type="early",
            quantity=2,
            price_per_ticket=10.0,
            boys=1,
            girls=1,
            attendees=[{"name": "A", "surname": "One"}, {"name": "B", "surname": "Two"}],
        )
        event = self.db.get_event(self.event_id)
        self.assertEqual(event.early_bird_qty, 3)
        self.assertEqual(reservation.total_price, 20.0)

    def test_cancel_returns_early_bird(self):
        reservation = self.db.reserve_event(
            user_id=self.user_id,
            event_id=self.event_id,
            ticket_type="early",
            quantity=2,
            price_per_ticket=10.0,
            boys=1,
            girls=1,
            attendees=[{"name": "A", "surname": "One"}, {"name": "B", "surname": "Two"}],
        )
        self.db.cancel_reservation(reservation.id)
        event = self.db.get_event(self.event_id)
        self.assertEqual(event.early_bird_qty, 5)


if __name__ == "__main__":
    unittest.main()
