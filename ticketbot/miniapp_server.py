import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ticketbot.database import Database

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "miniapp"

load_dotenv()
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.db")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
db = Database(DATABASE_PATH)

app = FastAPI(title="TicketBot Mini App Server")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def _event_payload(event) -> Dict[str, Any]:
    tier = db.active_tier(event)
    return {
        "id": event.id,
        "title": event.title,
        "event_datetime": event.event_datetime,
        "location": event.location,
        "caption": event.caption,
        "photo_file_id": event.photo_file_id,
        "tier": tier,
    }


class QuoteRequest(BaseModel):
    event_id: int
    boys: int = Field(ge=0)
    girls: int = Field(ge=0)


class AdminGuestAddRequest(BaseModel):
    tg_id: int
    reservation_code: str
    gender: str
    full_name: str


class AdminGuestRemoveRequest(BaseModel):
    tg_id: int
    attendee_id: int


class AdminGuestRenameRequest(BaseModel):
    tg_id: int
    attendee_id: int
    full_name: str


class AdminEventUpdateRequest(BaseModel):
    tg_id: int
    event_id: int
    updates: Dict[str, Any]


def _require_admin(tg_id: Optional[int]) -> int:
    if tg_id is None:
        raise HTTPException(status_code=401, detail="Missing tg_id.")
    if tg_id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Admin access denied.")
    return tg_id


def _row_dict(row) -> Dict[str, Any]:
    return dict(row) if row is not None else {}


@app.get("/")
def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(WEB_DIR / "admin.html")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/events")
def list_events() -> Dict[str, Any]:
    items = []
    for event in db.list_events():
        payload = _event_payload(event)
        if payload["tier"]:
            items.append(payload)
    return {"items": items}


@app.post("/api/quote")
def quote(payload: QuoteRequest) -> Dict[str, Any]:
    event = db.get_event(payload.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    tier = db.active_tier(event)
    if not tier:
        raise HTTPException(status_code=409, detail="Event is sold out.")

    quantity = payload.boys + payload.girls
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Total attendees must be at least 1.")
    if quantity > tier["remaining"]:
        raise HTTPException(status_code=400, detail="Not enough tickets in current tier.")

    total = payload.boys * tier["boy_price"] + payload.girls * tier["girl_price"]
    return {
        "event_id": event.id,
        "event_title": event.title,
        "tier": tier,
        "boys": payload.boys,
        "girls": payload.girls,
        "quantity": quantity,
        "total_price": total,
    }


@app.get("/api/admin/bootstrap")
def admin_bootstrap(tg_id: int) -> Dict[str, Any]:
    _require_admin(tg_id)
    return {"ok": True, "tg_id": tg_id}


@app.get("/api/admin/guests")
def admin_guests(
    tg_id: int,
    sort_by: str = "newest",
    search: Optional[str] = None,
    limit: int = 40,
) -> Dict[str, Any]:
    _require_admin(tg_id)
    rows = db.list_guests(sort_by=sort_by, search=search, limit=limit)
    return {"items": [_row_dict(r) for r in rows]}


@app.get("/api/admin/reservations")
def admin_reservations(tg_id: int, search: Optional[str] = None, limit: int = 25) -> Dict[str, Any]:
    _require_admin(tg_id)
    rows = db.list_active_reservations(search=search, limit=limit)
    return {"items": [_row_dict(r) for r in rows]}


@app.get("/api/admin/events")
def admin_events(tg_id: int) -> Dict[str, Any]:
    _require_admin(tg_id)
    items = []
    for event in db.list_events():
        payload = _event_payload(event)
        payload["prices"] = {
            "early_boy": event.early_bird_price,
            "early_girl": event.early_bird_price_girl,
            "early_qty": event.early_bird_qty,
            "tier1_boy": event.regular_tier1_price,
            "tier1_girl": event.regular_tier1_price_girl,
            "tier1_qty": event.regular_tier1_qty,
            "tier2_boy": event.regular_tier2_price,
            "tier2_girl": event.regular_tier2_price_girl,
            "tier2_qty": event.regular_tier2_qty,
        }
        items.append(payload)
    return {"items": items}


@app.post("/api/admin/guest/add")
def admin_guest_add(payload: AdminGuestAddRequest) -> Dict[str, Any]:
    _require_admin(payload.tg_id)
    ok, message, reservation = db.admin_add_guest(
        reservation_code=payload.reservation_code.strip(),
        full_name=payload.full_name.strip(),
        gender_raw=payload.gender.strip().lower(),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "reservation": reservation.__dict__ if reservation else None}


@app.post("/api/admin/guest/remove")
def admin_guest_remove(payload: AdminGuestRemoveRequest) -> Dict[str, Any]:
    _require_admin(payload.tg_id)
    ok, message, reservation = db.admin_remove_guest(payload.attendee_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "reservation": reservation.__dict__ if reservation else None}


@app.post("/api/admin/guest/rename")
def admin_guest_rename(payload: AdminGuestRenameRequest) -> Dict[str, Any]:
    _require_admin(payload.tg_id)
    ok, message = db.admin_rename_guest(payload.attendee_id, payload.full_name.strip())
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message}


@app.post("/api/admin/event/update")
def admin_event_update(payload: AdminEventUpdateRequest) -> Dict[str, Any]:
    _require_admin(payload.tg_id)
    ok, message = db.set_event_fields(event_id=payload.event_id, updates=payload.updates)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    event = db.get_event(payload.event_id)
    return {"ok": True, "message": message, "event": event.__dict__ if event else None}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("MINI_APP_HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("MINI_APP_PORT", "8080"))
    reload_enabled = os.getenv("MINI_APP_RELOAD", "0") == "1"
    uvicorn.run("ticketbot.miniapp_server:app", host=host, port=port, reload=reload_enabled)
