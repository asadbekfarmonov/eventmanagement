import os
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook, load_workbook
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


def _tier_label(tier_key: str) -> str:
    labels = {
        "early": "Early Bird",
        "tier1": "Regular Tier-1",
        "tier2": "Regular Tier-2",
    }
    return labels.get(tier_key, tier_key)


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


class AdminEventCreateSimpleRequest(BaseModel):
    tg_id: int
    title: str
    caption: str = ""
    early_boy: float = Field(ge=0)
    early_girl: float = Field(ge=0)
    early_qty: int = Field(ge=0)
    tier1_boy: float = Field(ge=0)
    tier1_girl: float = Field(ge=0)
    tier1_qty: int = Field(ge=0)
    tier2_boy: float = Field(ge=0)
    tier2_girl: float = Field(ge=0)
    tier2_qty: int = Field(ge=0)
    location: Optional[str] = None
    event_datetime: Optional[str] = None


class AdminGuestAddByEventRequest(BaseModel):
    tg_id: int
    event_id: int
    name: str
    surname: str
    gender: str


class AdminGuestRemoveByNameRequest(BaseModel):
    tg_id: int
    event_id: int
    name: str
    surname: str


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


@app.get("/api/me")
def me(tg_id: int) -> Dict[str, Any]:
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found. Run /start in bot.")
    return {
        "profile": {
            "tg_id": user.tg_id,
            "name": user.name,
            "surname": user.surname,
            "phone": user.phone,
        }
    }


@app.get("/api/my_tickets")
def my_tickets(tg_id: int, limit: int = 20) -> Dict[str, Any]:
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found. Run /start in bot.")
    rows = db.list_reservations_for_user(user.id)[: max(1, min(limit, 100))]
    items = []
    for reservation in rows:
        event = db.get_event(reservation.event_id)
        attendees = db.list_attendees(reservation.id)
        items.append(
            {
                "code": reservation.code,
                "event_id": reservation.event_id,
                "event_title": event.title if event else f"Event #{reservation.event_id}",
                "status": reservation.status,
                "tier_label": _tier_label(reservation.ticket_type),
                "boys": reservation.boys,
                "girls": reservation.girls,
                "total_price": reservation.total_price,
                "attendees": [row["full_name"] for row in attendees],
            }
        )
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


@app.post("/api/admin/guest/add_by_event")
def admin_guest_add_by_event(payload: AdminGuestAddByEventRequest) -> Dict[str, Any]:
    _require_admin(payload.tg_id)
    ok, message, reservation = db.admin_add_guest_by_event(
        admin_tg_id=payload.tg_id,
        event_id=payload.event_id,
        name=payload.name.strip(),
        surname=payload.surname.strip(),
        gender_raw=payload.gender.strip().lower(),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "reservation": reservation.__dict__ if reservation else None}


@app.post("/api/admin/guest/remove_by_name")
def admin_guest_remove_by_name(payload: AdminGuestRemoveByNameRequest) -> Dict[str, Any]:
    _require_admin(payload.tg_id)
    ok, message, reservation = db.admin_remove_guest_by_name(
        event_id=payload.event_id,
        name=payload.name.strip(),
        surname=payload.surname.strip(),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "reservation": reservation.__dict__ if reservation else None}


@app.post("/api/admin/guest/import_xlsx")
async def admin_guest_import_xlsx(
    tg_id: int = Form(...),
    event_id: int = Form(...),
    gender: str = Form("girl"),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    _require_admin(tg_id)
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Upload .xlsx file.")

    raw = await file.read()
    try:
        workbook = load_workbook(filename=BytesIO(raw), data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse xlsx: {exc}") from exc

    sheet = workbook.active
    added = 0
    skipped = 0
    errors = []

    for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        value_name = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
        value_surname = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        if not value_name and not value_surname:
            continue
        if row_index == 1 and value_name.lower() in {"name", "first_name"} and value_surname.lower() in {
            "surname",
            "last_name",
        }:
            continue
        if not value_name or not value_surname:
            skipped += 1
            errors.append(f"Row {row_index}: missing name or surname.")
            continue

        ok, message, _reservation = db.admin_add_guest_by_event(
            admin_tg_id=tg_id,
            event_id=event_id,
            name=value_name,
            surname=value_surname,
            gender_raw=gender,
        )
        if ok:
            added += 1
        else:
            skipped += 1
            errors.append(f"Row {row_index}: {message}")

    return {
        "ok": True,
        "added": added,
        "skipped": skipped,
        "errors": errors[:10],
    }


@app.get("/api/admin/guest/export_xlsx")
def admin_guest_export_xlsx(tg_id: int) -> StreamingResponse:
    _require_admin(tg_id)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Guests"
    sheet.append(["Name", "Surname"])
    for first, last in db.list_guest_name_pairs():
        sheet.append([first, last])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="guests_export.xlsx"'}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@app.post("/api/admin/event/update")
def admin_event_update(payload: AdminEventUpdateRequest) -> Dict[str, Any]:
    _require_admin(payload.tg_id)
    ok, message = db.set_event_fields(event_id=payload.event_id, updates=payload.updates)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    event = db.get_event(payload.event_id)
    return {"ok": True, "message": message, "event": event.__dict__ if event else None}


@app.post("/api/admin/event/create_simple")
def admin_event_create_simple(payload: AdminEventCreateSimpleRequest) -> Dict[str, Any]:
    _require_admin(payload.tg_id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required.")

    total_qty = int(payload.early_qty) + int(payload.tier1_qty) + int(payload.tier2_qty)
    if total_qty <= 0:
        raise HTTPException(status_code=400, detail="At least one ticket quantity must be greater than 0.")

    location = (payload.location or "Budapest").strip() or "Budapest"
    if payload.event_datetime:
        event_datetime = payload.event_datetime.strip()
        try:
            db.parse_event_datetime(event_datetime)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid datetime format. Use YYYY-MM-DD HH:MM") from exc
    else:
        default_dt = (datetime.now(ZoneInfo("Europe/Budapest")) + timedelta(days=7)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        event_datetime = default_dt.strftime("%Y-%m-%d %H:%M")

    event_id = db.create_event(
        title=title,
        event_datetime=event_datetime,
        location=location,
        caption=payload.caption.strip(),
        photo_file_id="",
        early_boy_price=float(payload.early_boy),
        early_girl_price=float(payload.early_girl),
        early_qty=int(payload.early_qty),
        tier1_boy_price=float(payload.tier1_boy),
        tier1_girl_price=float(payload.tier1_girl),
        tier1_qty=int(payload.tier1_qty),
        tier2_boy_price=float(payload.tier2_boy),
        tier2_girl_price=float(payload.tier2_girl),
        tier2_qty=int(payload.tier2_qty),
    )
    event = db.get_event(event_id)
    return {
        "ok": True,
        "message": "Event created.",
        "event": event.__dict__ if event else None,
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("MINI_APP_HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("MINI_APP_PORT", "8080"))
    reload_enabled = os.getenv("MINI_APP_RELOAD", "0") == "1"
    uvicorn.run("ticketbot.miniapp_server:app", host=host, port=port, reload=reload_enabled)
