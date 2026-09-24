import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest import mock

from fastapi.testclient import TestClient

BUDAPEST_TZ = ZoneInfo("Europe/Budapest")


def _future_datetime(hours: float) -> str:
    return (datetime.now(BUDAPEST_TZ) + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")


class TicketChangeAdversarialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "adv.db")
        self.admin_tg_id = 7164876915
        self.user_tg_id = 511308234
        keys = ("DATABASE_PATH","ADMIN_IDS","BOT_TOKEN","MINIAPP_ALLOW_TG_ID_FALLBACK",
                "WEB_APP_URL","UPLOAD_DIR","ADMIN_WEB_PASSWORD","EMAIL_LOGIN_DEV_MODE",
                "TICKET_MOVE_MIN_HOURS","TICKET_REFUND_MIN_HOURS")
        self._backup = {k: os.environ.get(k) for k in keys}
        os.environ.update({
            "DATABASE_PATH": self.db_path, "ADMIN_IDS": str(self.admin_tg_id),
            "BOT_TOKEN": "dummy-token", "MINIAPP_ALLOW_TG_ID_FALLBACK": "1",
            "WEB_APP_URL": "https://example.invalid",
            "UPLOAD_DIR": os.path.join(self.temp_dir.name, "up"),
            "ADMIN_WEB_PASSWORD": "pw", "EMAIL_LOGIN_DEV_MODE": "1",
            "TICKET_MOVE_MIN_HOURS": "24", "TICKET_REFUND_MIN_HOURS": "72",
        })
        import ticketbot.miniapp_server as m
        self.server = importlib.reload(m)
        self.client = TestClient(self.server.app)
        self.db = self.server.db
        self.db.upsert_user(self.user_tg_id, "Buyer", "User", "+36 20 111 2222")
        self.user_id = self.db.get_user(self.user_tg_id).id

    def tearDown(self) -> None:
        self.client.close()
        for k, v in self._backup.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        self.temp_dir.cleanup()

    def _event(self, h): 
        return self.db.create_event(title="P", event_datetime=_future_datetime(h),
            location="B", caption="c", photo_file_id="",
            early_boy_price=1.0, early_girl_price=1.0, early_qty=10,
            tier1_boy_price=1.0, tier1_girl_price=1.0, tier1_qty=0,
            tier2_boy_price=1.0, tier2_girl_price=1.0, tier2_qty=0)

    def _res(self):
        r = self.db.create_pending_reservation(user_id=self.user_id, event_id=self._event(100),
            boys=1, girls=0, attendees=["G"], payment_file_id="p", payment_file_type="photo")
        ok, _msg, appr = self.db.approve_reservation(r.id, self.admin_tg_id)
        return appr

    def _req(self, code, kind):
        return self.client.post("/api/web/ticket/request",
            params={"tg_id": self.user_tg_id},
            json={"code": code, "kind": kind, "tg_id": self.user_tg_id})

    def test_second_different_kind_does_not_overwrite(self):
        res = self._res()
        self.assertEqual(self._req(res.code, "move").status_code, 200)
        second = self._req(res.code, "refund")
        stored = self.db.get_reservation_by_code(res.code)
        # A ticket that already has a pending change request must not be silently
        # overwritten to a different kind by a direct POST.
        self.assertEqual(stored.change_request, "move",
                         f"change_request was overwritten to {stored.change_request!r}; got HTTP {second.status_code}")

    def test_repeat_does_not_refire_admin_notification(self):
        res = self._res()
        with mock.patch.object(self.server, "_bot_api") as bot:
            self._req(res.code, "move")
            first_calls = bot.call_count
            self._req(res.code, "move")
            total = bot.call_count
        self.assertEqual(total, first_calls,
                         f"admin notification re-fired on repeat request: {first_calls} -> {total}")


if __name__ == "__main__":
    unittest.main()
