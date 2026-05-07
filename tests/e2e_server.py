import os
import sys
import tempfile
from pathlib import Path

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
    os.environ["WEB_APP_URL"] = "http://127.0.0.1:8000"
    os.environ["UPLOAD_MAX_MB"] = "5"
    os.environ["UPLOAD_RETENTION_DAYS"] = "7"
    os.environ["UPLOAD_CLEANUP_INTERVAL_SECONDS"] = "3600"

    import ticketbot.miniapp_server as miniapp_server

    db = miniapp_server.db
    db.upsert_user(511308234, "Buyer", "User", "phone")
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
    db.create_event(
        title="Discount Event",
        event_datetime="2026-03-04 16:00",
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

    uvicorn.run(miniapp_server.app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
