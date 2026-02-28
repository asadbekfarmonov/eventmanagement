import os
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional
import json
import uuid
import urllib.request
import urllib.error
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
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEB_APP_URL = os.getenv("WEB_APP_URL", "").rstrip("/")
DEFAULT_UPLOAD_DIR = str(Path(DATABASE_PATH).resolve().parent / "uploads")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", DEFAULT_UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)
db = Database(DATABASE_PATH)

app = FastAPI(title="TicketBot Mini App Server")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


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


def _bot_api(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN is missing"}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return {"ok": False}


def _notify_admins_pending_from_miniapp(reservation) -> None:
    event = db.get_event(reservation.event_id)
    user = db.get_user_by_id(reservation.user_id)
    attendees = db.list_attendees(reservation.id)
    attendee_lines = "\n".join([f"- {row['full_name']}" for row in attendees]) if attendees else "-"
    event_title = event.title if event else f"Event #{reservation.event_id}"
    tier_label = _tier_label(reservation.ticket_type)
    buyer = "Unknown"
    if user:
        buyer = f"{user.name} {user.surname} (tg:{user.tg_id})"

    caption = (
        "New payment proof pending review\n\n"
        f"Code: {reservation.code}\n"
        f"Event: {event_title}\n"
        f"Tier: {tier_label}\n"
        f"Boys: {reservation.boys} | Girls: {reservation.girls}\n"
        f"Total: {reservation.total_price:.2f}\n"
        f"Buyer: {buyer}\n\n"
        f"Attendees:\n{attendee_lines}\n\n"
        f"Payment proof: {reservation.payment_file_id}"
    )
    buttons = {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": f"review:approve:{reservation.id}"},
                {"text": "Reject Unreadable", "callback_data": f"review:reject:tpl:unreadable:{reservation.id}"},
            ],
            [
                {"text": "Reject Amount", "callback_data": f"review:reject:tpl:amount:{reservation.id}"},
                {"text": "Reject Custom", "callback_data": f"review:reject:custom:{reservation.id}"},
            ],
        ]
    }
    for admin_id in ADMIN_IDS:
        _bot_api(
            "sendMessage",
            {
                "chat_id": admin_id,
                "text": caption,
                "reply_markup": buttons,
                "disable_web_page_preview": False,
            },
        )


def _notify_user_pending_from_miniapp(reservation, tg_id: int) -> None:
    _bot_api(
        "sendMessage",
        {
            "chat_id": tg_id,
            "text": f"Your booking is pending admin approval.\nCode: {reservation.code}",
        },
    )


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


def _normalize_header_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("\ufeff", "")


def _parse_guest_row(row: tuple, row_index: int) -> Dict[str, Any]:
    value_name = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
    value_surname = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""

    if not value_name and not value_surname:
        return {"skip": True, "reason": "empty"}

    if row_index == 1:
        h1 = _normalize_header_cell(value_name)
        h2 = _normalize_header_cell(value_surname)
        if h1 in {"name", "first_name", "firstname", "first name", "isim", "имя"} and h2 in {
            "surname",
            "last_name",
            "lastname",
            "last name",
            "soyad",
            "фамилия",
        }:
            return {"skip": True, "reason": "header"}

    if value_name and not value_surname and " " in value_name:
        parts = [p for p in value_name.split() if p]
        if len(parts) >= 2:
            value_name = parts[0]
            value_surname = " ".join(parts[1:])

    if not value_name and value_surname:
        value_name = value_surname
        value_surname = ""

    if not value_name:
        return {"skip": True, "reason": "missing_name"}

    return {
        "skip": False,
        "name": value_name,
        "surname": value_surname,
    }


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


@app.post("/api/book_with_payment")
async def book_with_payment(
    tg_id: int = Form(...),
    event_id: int = Form(...),
    boys: int = Form(...),
    girls: int = Form(...),
    attendees: str = Form(...),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found. Run /start in bot.")

    try:
        attendees_list = json.loads(attendees)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="attendees must be valid JSON list.") from exc
    if not isinstance(attendees_list, list):
        raise HTTPException(status_code=400, detail="attendees must be a list.")
    normalized_attendees = [str(x).strip() for x in attendees_list]
    if any(len(name.split()) < 2 for name in normalized_attendees):
        raise HTTPException(status_code=400, detail='Each attendee must be in format "Name Surname".')

    mime = (file.content_type or "").lower()
    if not (mime.startswith("image/") or mime == "application/pdf"):
        raise HTTPException(status_code=400, detail="Only image or PDF is accepted.")

    suffix = ".pdf" if mime == "application/pdf" else ".jpg"
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = Path(UPLOAD_DIR) / stored_name
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    stored_path.write_bytes(content)

    proof_url = f"/uploads/{stored_name}"
    if WEB_APP_URL:
        proof_url = f"{WEB_APP_URL}{proof_url}"

    try:
        reservation = db.create_pending_reservation(
            user_id=user.id,
            event_id=int(event_id),
            boys=int(boys),
            girls=int(girls),
            attendees=normalized_attendees,
            payment_file_id=proof_url,
            payment_file_type="external",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _notify_admins_pending_from_miniapp(reservation)
    _notify_user_pending_from_miniapp(reservation, tg_id)
    return {
        "ok": True,
        "code": reservation.code,
        "status": reservation.status,
    }


@app.post("/api/quote")
def quote(payload: QuoteRequest) -> Dict[str, Any]:
    try:
        return db.quote_booking(payload.event_id, payload.boys, payload.girls)
    except ValueError as exc:
        text = str(exc)
        if text == "Event not found":
            raise HTTPException(status_code=404, detail=text) from exc
        if "sold out" in text.lower() or "not enough tickets" in text.lower():
            raise HTTPException(status_code=409, detail=text) from exc
        raise HTTPException(status_code=400, detail=text) from exc


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
        parsed = _parse_guest_row(row, row_index)
        if parsed["skip"]:
            if parsed["reason"] in {"empty", "header"}:
                continue
            skipped += 1
            errors.append(f"Row {row_index}: invalid name/surname values.")
            continue

        value_name = parsed["name"]
        value_surname = parsed["surname"]

        ok, message, _reservation = db.admin_add_guest_by_event(
            admin_tg_id=tg_id,
            event_id=event_id,
            name=value_name,
            surname=value_surname,
            gender_raw=gender,
            allow_missing_surname=True,
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
