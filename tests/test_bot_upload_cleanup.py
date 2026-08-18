import asyncio
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

    def test_notify_user_after_review_skips_web_buyer_with_negative_tg_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "bot.db")
            bot = TelegramBot(
                Config(
                    bot_token="test-token",
                    admin_ids=set(),
                    database_path=db_path,
                    web_app_url=None,
                )
            )

            class _RecordingBot:
                def __init__(self):
                    self.calls = []

                async def send_message(self, *args, **kwargs):
                    self.calls.append(kwargs or args)
                    raise RuntimeError("Chat not found")

            class _Application:
                def __init__(self, bot):
                    self.bot = bot

            recording_bot = _RecordingBot()
            bot.application = _Application(recording_bot)

            # Web buyers are stored with a negative tg_id.
            web_tg_id = -511308234
            bot.db.upsert_user(web_tg_id, "Web", "Buyer", "phone")
            user = bot.db.get_user(web_tg_id)
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

            # Must not raise and must not attempt delivery to a non-positive tg_id.
            asyncio.run(bot._notify_user_after_review(reservation, approved=True, note=""))
            self.assertEqual(recording_bot.calls, [])

    def test_notify_user_after_review_swallows_send_failure_for_real_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "bot.db")
            bot = TelegramBot(
                Config(
                    bot_token="test-token",
                    admin_ids=set(),
                    database_path=db_path,
                    web_app_url=None,
                )
            )

            class _FailingBot:
                def __init__(self):
                    self.calls = []

                async def send_message(self, *args, **kwargs):
                    self.calls.append(kwargs or args)
                    raise RuntimeError("Chat not found")

            class _Application:
                def __init__(self, bot):
                    self.bot = bot

            failing_bot = _FailingBot()
            bot.application = _Application(failing_bot)

            bot.db.upsert_user(222, "Real", "User", "phone")
            user = bot.db.get_user(222)
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

            # A delivery failure for a real user must be swallowed (no raise).
            asyncio.run(bot._notify_user_after_review(reservation, approved=False, note="bad"))
            self.assertEqual(len(failing_bot.calls), 1)


class BotAdminReviewCleanupPathTests(unittest.TestCase):
    """H4: the approve/reject cleanup path must NOT be skipped when a Telegram
    admin reviews a WEB booking (buyer has a non-positive tg_id), nor when the
    Telegram delivery fails for a real buyer."""

    def _make_bot_with_web_reservation(self, tmp, *, tg_id, admin_id):
        db_path = os.path.join(tmp, "bot.db")
        upload_dir = Path(tmp) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        proof_path = upload_dir / "proof.jpg"
        proof_path.write_bytes(b"proof-bytes")

        os.environ["UPLOAD_DIR"] = str(upload_dir)
        bot = TelegramBot(
            Config(
                bot_token="test-token",
                admin_ids={admin_id},
                database_path=db_path,
                web_app_url=None,
            )
        )
        bot.db.upsert_user(tg_id, "Web", "Buyer", "phone")
        user = bot.db.get_user(tg_id)
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
        return bot, reservation, proof_path

    @staticmethod
    def _make_query(data):
        class _Query:
            def __init__(self, data):
                self.data = data
                self.markup_cleared = False
                self.replies = []
                self.answered = False
                self.message = self

            async def answer(self, *a, **k):
                self.answered = True

            async def reply_text(self, text, *a, **k):
                self.replies.append(text)

            async def edit_message_reply_markup(self, reply_markup=None):
                self.markup_cleared = reply_markup is None

        return _Query(data)

    @staticmethod
    def _make_update(query, admin_id):
        class _User:
            def __init__(self, uid):
                self.id = uid

        class _Update:
            def __init__(self, query, uid):
                self.callback_query = query
                self.effective_user = _User(uid)

        return _Update(query, admin_id)

    def test_admin_approve_web_buyer_still_deletes_file_and_clears_markup(self):
        admin_id = 999
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("UPLOAD_DIR")
            try:
                # Web buyer -> negative tg_id (must not attempt delivery, must not crash).
                bot, reservation, proof_path = self._make_bot_with_web_reservation(
                    tmp, tg_id=-511308234, admin_id=admin_id
                )

                # Guard: if this path ever tried to deliver, it would explode.
                class _Boom:
                    async def send_message(self, *a, **k):
                        raise AssertionError("must not deliver to web buyer")

                class _App:
                    bot = _Boom()

                bot.application = _App()

                query = self._make_query(f"review:approve:{reservation.id}")
                update = self._make_update(query, admin_id)

                self.assertTrue(proof_path.exists())
                asyncio.run(bot.admin_approve(update, None))

                # Cleanup path must have run despite the web buyer.
                self.assertFalse(proof_path.exists(), "external proof file was not deleted")
                self.assertTrue(query.markup_cleared, "inline keyboard markup was not cleared")
                self.assertEqual(
                    bot.db.get_reservation(reservation.id).status, "approved"
                )
            finally:
                if old is None:
                    os.environ.pop("UPLOAD_DIR", None)
                else:
                    os.environ["UPLOAD_DIR"] = old

    def test_admin_reject_real_buyer_send_failure_still_cleans_up(self):
        admin_id = 999
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("UPLOAD_DIR")
            try:
                bot, reservation, proof_path = self._make_bot_with_web_reservation(
                    tmp, tg_id=222, admin_id=admin_id
                )

                class _Failing:
                    def __init__(self):
                        self.calls = 0

                    async def send_message(self, *a, **k):
                        self.calls += 1
                        raise RuntimeError("Chat not found")

                class _App:
                    def __init__(self, b):
                        self.bot = b

                failing = _Failing()
                bot.application = _App(failing)

                query = self._make_query(f"review:reject:tpl:unreadable:{reservation.id}")
                update = self._make_update(query, admin_id)

                self.assertTrue(proof_path.exists())
                asyncio.run(bot.admin_reject_template(update, None))

                # Delivery was attempted (real positive tg_id) but failed and was swallowed.
                self.assertEqual(failing.calls, 1)
                self.assertFalse(proof_path.exists(), "external proof file was not deleted")
                self.assertTrue(query.markup_cleared, "inline keyboard markup was not cleared")
                self.assertEqual(
                    bot.db.get_reservation(reservation.id).status, "rejected"
                )
            finally:
                if old is None:
                    os.environ.pop("UPLOAD_DIR", None)
                else:
                    os.environ["UPLOAD_DIR"] = old


if __name__ == "__main__":
    unittest.main()
