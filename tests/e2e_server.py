import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    temp_root = Path(tempfile.mkdtemp(prefix="eventmanagement-e2e-"))
    os.environ["DATABASE_PATH"] = str(temp_root / "e2e.db")
    os.environ["UPLOAD_DIR"] = str(temp_root / "uploads")
    os.environ["ADMIN_IDS"] = "7164876915"
    os.environ["BOT_TOKEN"] = ""
    os.environ["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "1"
    os.environ["WEB_APP_URL"] = "http://127.0.0.1:8000"
    os.environ["UPLOAD_MAX_MB"] = "5"
    os.environ["UPLOAD_RETENTION_DAYS"] = "7"
    os.environ["UPLOAD_CLEANUP_INTERVAL_SECONDS"] = "3600"
    os.environ["ADMIN_WEB_PASSWORD"] = "playwright-admin-password"
    os.environ["GUARD_WEB_PASSWORD"] = "playwright-guard-password"
    os.environ["EMAIL_LOGIN_DEV_MODE"] = "1"
    os.environ["EMAIL_LOGIN_TTL_SECONDS"] = "600"
    os.environ["EMAIL_LOGIN_RATE_LIMIT"] = "20"

    import ticketbot.miniapp_server as miniapp_server

    db = miniapp_server.db
    db.upsert_user(511308234, "Buyer", "User", "phone")
    # A far-future date so the seeded approved ticket below is eligible for both
    # the move (24h) and refund (72h) requests regardless of when the suite runs.
    future_dt = (datetime.now(ZoneInfo("Europe/Budapest")) + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    db.create_event(
        title="Playwright Event",
        event_datetime="2026-03-03 16:00",
        location="Budapest",
        caption="Seeded event for browser E2E",
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
    discount_event_id = db.create_event(
        title="Discount Event",
        event_datetime=future_dt,
        location="Budapest",
        caption="Seeded discount event for browser E2E",
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
        repost_discount_enabled=True,
        repost_discount_amount=1000.0,
    )

    # Seed an APPROVED ticket for the tg user on the far-future Discount Event so
    # the "My tickets" move/refund request buttons are exercised by E2E. No test
    # submits a Discount Event booking, so this stays the only Discount Event card.
    buyer = db.get_user(511308234)
    approved_reservation = db.create_pending_reservation(
        user_id=buyer.id,
        event_id=discount_event_id,
        boys=1,
        girls=0,
        attendees=["Buyer User"],
        payment_file_id="proof",
        payment_file_type="photo",
    )
    db.approve_reservation(approved_reservation.id, 7164876915)

    uvicorn.run(miniapp_server.app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
