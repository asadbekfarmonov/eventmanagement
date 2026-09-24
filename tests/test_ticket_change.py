import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

BUDAPEST_TZ = ZoneInfo("Europe/Budapest")


def _future_datetime(hours: float) -> str:
    """Return an event_datetime string N hours from now in Europe/Budapest."""
    return (datetime.now(BUDAPEST_TZ) + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")


class TicketChangeRequestTests(unittest.TestCase):
    """Move/refund request window, ownership, status and eligibility flags."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "ticket_change_test.db")
        self.admin_tg_id = 7164876915
        self.user_tg_id = 511308234
        self.other_tg_id = 222333444
        self.admin_password = "test-admin-password"
        self._env_keys = (
            "DATABASE_PATH",
            "ADMIN_IDS",
            "BOT_TOKEN",
            "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL",
            "UPLOAD_DIR",
            "ADMIN_WEB_PASSWORD",
            "EMAIL_LOGIN_DEV_MODE",
            "TICKET_MOVE_MIN_HOURS",
            "TICKET_REFUND_MIN_HOURS",
        )
        self._env_backup = {key: os.environ.get(key) for key in self._env_keys}
        os.environ["DATABASE_PATH"] = self.db_path
        os.environ["ADMIN_IDS"] = str(self.admin_tg_id)
        os.environ["BOT_TOKEN"] = ""
        os.environ["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "1"
        os.environ["WEB_APP_URL"] = "https://example.invalid"
        os.environ["UPLOAD_DIR"] = os.path.join(self.temp_dir.name, "uploads")
        os.environ["ADMIN_WEB_PASSWORD"] = self.admin_password
        os.environ["EMAIL_LOGIN_DEV_MODE"] = "1"
        os.environ["TICKET_MOVE_MIN_HOURS"] = "24"
        os.environ["TICKET_REFUND_MIN_HOURS"] = "72"

        import ticketbot.miniapp_server as miniapp_server

        self.server = importlib.reload(miniapp_server)
        self.client = TestClient(self.server.app)
        self.db = self.server.db

        self.db.upsert_user(self.user_tg_id, "Buyer", "User", "+36 20 111 2222")
        self.user_id = self.db.get_user(self.user_tg_id).id
        self.db.upsert_user(self.other_tg_id, "Other", "Person", "+36 20 999 8888")
        self.other_user_id = self.db.get_user(self.other_tg_id).id

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

    def _create_event(self, hours_ahead: float) -> int:
        return self.db.create_event(
            title="Future Party",
            event_datetime=_future_datetime(hours_ahead),
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

    def _create_reservation(self, event_id, user_id=None, status="approved"):
        user_id = user_id if user_id is not None else self.user_id
        reservation = self.db.create_pending_reservation(
            user_id=user_id,
            event_id=event_id,
            boys=1,
            girls=0,
            attendees=["Guest One"],
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

    def _request(self, code, kind, tg_id=None):
        tg_id = tg_id if tg_id is not None else self.user_tg_id
        return self.client.post(
            "/api/web/ticket/request",
            params={"tg_id": tg_id},
            json={"code": code, "kind": kind, "tg_id": tg_id},
        )

    def _my_ticket_item(self, code, tg_id=None):
        tg_id = tg_id if tg_id is not None else self.user_tg_id
        resp = self.client.get("/api/my_tickets", params={"tg_id": tg_id})
        self.assertEqual(resp.status_code, 200, resp.text)
        for item in resp.json()["items"]:
            if item["code"] == code:
                return item
        return None

    # ---- window enforcement ------------------------------------------------

    def test_far_future_allows_move_and_refund(self) -> None:
        reservation = self._create_reservation(self._create_event(100))
        for kind in ("move", "refund"):
            res = self._create_reservation(self._create_event(100))
            resp = self._request(res.code, kind)
            self.assertEqual(resp.status_code, 200, resp.text)
            self.assertEqual(resp.json()["change_request"], kind)
        # eligibility flags for a fresh far-future ticket
        item = self._my_ticket_item(reservation.code)
        self.assertTrue(item["can_request_move"])
        self.assertTrue(item["can_request_refund"])
        self.assertEqual(item["move_min_hours"], 24)
        self.assertEqual(item["refund_min_hours"], 72)

    def test_mid_window_allows_move_not_refund(self) -> None:
        reservation = self._create_reservation(self._create_event(50))
        item = self._my_ticket_item(reservation.code)
        self.assertTrue(item["can_request_move"])
        self.assertFalse(item["can_request_refund"])
        # refund rejected by the 72h window
        resp = self._request(reservation.code, "refund")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("72 hours", resp.json()["detail"])
        # move accepted
        resp = self._request(reservation.code, "move")
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_inside_move_window_allows_neither(self) -> None:
        reservation = self._create_reservation(self._create_event(10))
        item = self._my_ticket_item(reservation.code)
        self.assertFalse(item["can_request_move"])
        self.assertFalse(item["can_request_refund"])
        resp = self._request(reservation.code, "move")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("24 hours", resp.json()["detail"])
        resp = self._request(reservation.code, "refund")
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_past_event_allows_neither(self) -> None:
        reservation = self._create_reservation(self._create_event(-5))
        item = self._my_ticket_item(reservation.code)
        self.assertFalse(item["can_request_move"])
        self.assertFalse(item["can_request_refund"])
        resp = self._request(reservation.code, "move")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("already started", resp.json()["detail"])

    # ---- ownership ---------------------------------------------------------

    def test_other_users_code_returns_404(self) -> None:
        reservation = self._create_reservation(
            self._create_event(100), user_id=self.other_user_id
        )
        resp = self._request(reservation.code, "move", tg_id=self.user_tg_id)
        self.assertEqual(resp.status_code, 404, resp.text)

    # ---- status ------------------------------------------------------------

    def test_non_approved_status_returns_400(self) -> None:
        for status in ("pending", "rejected", "cancelled"):
            reservation = self._create_reservation(self._create_event(100), status=status)
            resp = self._request(reservation.code, "move")
            self.assertEqual(resp.status_code, 400, resp.text)
            self.assertEqual(
                resp.json()["detail"], "Only approved tickets can be moved or refunded."
            )

    def test_unknown_kind_returns_400(self) -> None:
        reservation = self._create_reservation(self._create_event(100))
        resp = self._request(reservation.code, "teleport")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(resp.json()["detail"], "Unknown request type.")

    # ---- records + eligibility reflect request -----------------------------

    def test_request_records_change_and_hides_buttons(self) -> None:
        reservation = self._create_reservation(self._create_event(100))
        resp = self._request(reservation.code, "move")
        self.assertEqual(resp.status_code, 200, resp.text)
        # DB round-trips the change_request and does NOT change status
        stored = self.db.get_reservation_by_code(reservation.code)
        self.assertEqual(stored.change_request, "move")
        self.assertTrue(stored.change_request_at)
        self.assertEqual(stored.status, "approved")
        # my_tickets now reflects the request and offers no more buttons
        item = self._my_ticket_item(reservation.code)
        self.assertEqual(item["change_request"], "move")
        self.assertFalse(item["can_request_move"])
        self.assertFalse(item["can_request_refund"])

    def test_repeat_request_is_idempotent(self) -> None:
        reservation = self._create_reservation(self._create_event(100))
        first = self._request(reservation.code, "move")
        self.assertEqual(first.status_code, 200, first.text)
        second = self._request(reservation.code, "move")
        self.assertEqual(second.status_code, 200, second.text)
        stored = self.db.get_reservation_by_code(reservation.code)
        self.assertEqual(stored.change_request, "move")


if __name__ == "__main__":
    unittest.main()
