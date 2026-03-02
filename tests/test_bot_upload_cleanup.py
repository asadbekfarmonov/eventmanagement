import os
import tempfile
import unittest
from pathlib import Path

from ticketbot.app import TelegramBot
from ticketbot.config import Config


class BotUploadCleanupTests(unittest.TestCase):
    def test_delete_external_payment_file_removes_local_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "bot.db")
            upload_dir = Path(tmp) / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            proof_path = upload_dir / "proof.jpg"
            proof_path.write_bytes(b"proof")

            old_upload_dir = os.environ.get("UPLOAD_DIR")
            os.environ["UPLOAD_DIR"] = str(upload_dir)
            try:
                bot = TelegramBot(
                    Config(
                        bot_token="test-token",
                        admin_ids=set(),
                        database_path=db_path,
                        web_app_url=None,
                    )
                )

                bot.db.upsert_user(111, "Test", "User", "phone")
                user = bot.db.get_user(111)
                event_id = bot.db.create_event(
                    title="T",
                    event_datetime="2026-03-03 16:00",
                    location="Budapest",
                    caption="C",
                    photo_file_id="",
                    early_boy_price=1000,
                    early_girl_price=1000,
                    early_qty=10,
                    tier1_boy_price=2000,
                    tier1_girl_price=2000,
                    tier1_qty=0,
                    tier2_boy_price=3000,
                    tier2_girl_price=3000,
                    tier2_qty=0,
                )
                reservation = bot.db.create_pending_reservation(
                    user_id=user.id,
                    event_id=event_id,
                    boys=1,
                    girls=0,
                    attendees=["John Doe"],
                    payment_file_id="/uploads/proof.jpg",
                    payment_file_type="external",
                )
                self.assertTrue(proof_path.exists())
                bot._delete_external_payment_file(reservation)
                self.assertFalse(proof_path.exists())
            finally:
                if old_upload_dir is None:
                    os.environ.pop("UPLOAD_DIR", None)
                else:
                    os.environ["UPLOAD_DIR"] = old_upload_dir


if __name__ == "__main__":
    unittest.main()
