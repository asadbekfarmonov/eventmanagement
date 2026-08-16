import os
import time
from datetime import datetime, timedelta
import hashlib
import hmac
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import uuid
import urllib.request
import urllib.error
from urllib.parse import parse_qsl, unquote, urlencode, urlparse
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook, load_workbook
from pydantic import BaseModel, Field
from starlette.datastructures import UploadFile as StarletteUploadFile

from ticketbot.database import Database, STATUS_PENDING

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "miniapp"

load_dotenv()
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.db")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEB_APP_URL = os.getenv("WEB_APP_URL", "").rstrip("/")
DEFAULT_UPLOAD_DIR = str(Path(DATABASE_PATH).resolve().parent / "uploads")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", DEFAULT_UPLOAD_DIR)
ALLOW_TG_ID_FALLBACK = os.getenv("MINIAPP_ALLOW_TG_ID_FALLBACK", "0").strip().lower() in {
    "1",
    "true",
    "yes",
}


def _env_positive_float(name: str, default: float) -> float:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_positive_int(name: str, default: int) -> int:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


UPLOAD_MAX_MB = _env_positive_float("UPLOAD_MAX_MB", 5.0)
MAX_UPLOAD_BYTES = int(UPLOAD_MAX_MB * 1024 * 1024)
TELEGRAM_AUTH_MAX_AGE_SECONDS = _env_positive_int("TELEGRAM_AUTH_MAX_AGE_SECONDS", 86400)
UPLOAD_RETENTION_DAYS = _env_positive_int("UPLOAD_RETENTION_DAYS", 7)
UPLOAD_CLEANUP_INTERVAL_SECONDS = _env_positive_int("UPLOAD_CLEANUP_INTERVAL_SECONDS", 3600)
UPLOAD_LINK_TTL_SECONDS = _env_positive_int("UPLOAD_LINK_TTL_SECONDS", UPLOAD_RETENTION_DAYS * 24 * 60 * 60)
RATE_LIMIT_WINDOW_SECONDS = _env_positive_int("RATE_LIMIT_WINDOW_SECONDS", 60)
QUOTE_RATE_LIMIT = _env_positive_int("QUOTE_RATE_LIMIT", 120)
BOOKING_RATE_LIMIT = _env_positive_int("BOOKING_RATE_LIMIT", 12)
_LAST_UPLOAD_CLEANUP_TS = 0.0
_RATE_LIMIT_BUCKETS: Dict[Tuple[str, str], List[float]] = {}

os.makedirs(UPLOAD_DIR, exist_ok=True)
db = Database(DATABASE_PATH)

app = FastAPI(title="TicketBot Mini App Server")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' https://telegram.org; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors https://web.telegram.org https://*.telegram.org;",
    )
    path = request.url.path
    if path in {"/", "/admin"} or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def _fallback_auth_allowed() -> bool:
    return ALLOW_TG_ID_FALLBACK or not BOT_TOKEN


def _parse_telegram_init_data(init_data: str) -> Dict[str, str]:
    return dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))


def _verify_telegram_init_data(init_data: str) -> Dict[str, Any]:
    if not BOT_TOKEN:
        raise HTTPException(status_code=503, detail="Telegram auth is not configured.")
    if not init_data:
        raise HTTPException(status_code=401, detail="Open this Mini App from Telegram.")

    parsed = _parse_telegram_init_data(init_data)
    received_hash = parsed.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=401, detail="Telegram auth hash is missing.")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=401, detail="Telegram auth is invalid.")

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Telegram auth date is invalid.") from exc
    if TELEGRAM_AUTH_MAX_AGE_SECONDS > 0 and time.time() - auth_date > TELEGRAM_AUTH_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Telegram session expired. Reopen the Mini App.")

    try:
        user = json.loads(parsed.get("user", "{}"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=401, detail="Telegram user data is invalid.") from exc
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=401, detail="Telegram user is missing.")
    return user


def _request_tg_id(request: Request, provided_tg_id: Optional[int]) -> int:
    init_data = request.headers.get("x-telegram-init-data", "")
    if init_data:
        user = _verify_telegram_init_data(init_data)
        verified_tg_id = int(user["id"])
        if provided_tg_id is not None and int(provided_tg_id) != verified_tg_id:
            raise HTTPException(status_code=403, detail="Telegram user mismatch.")
        return verified_tg_id
    if provided_tg_id is not None and _fallback_auth_allowed():
        return int(provided_tg_id)
    raise HTTPException(status_code=401, detail="Open this Mini App from Telegram.")


def _extract_upload_filename(payment_file_id: str) -> Optional[str]:
    raw = (payment_file_id or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme else raw
    if not path.startswith("/uploads/"):
        return None
    filename = unquote(Path(path).name)
    if not filename or filename in {".", ".."}:
        return None
    return filename


def _upload_signing_secret() -> bytes:
    secret = os.getenv("UPLOAD_LINK_SECRET", "") or BOT_TOKEN or "dev-upload-link-secret"
    return secret.encode("utf-8")


def _sign_upload(filename: str, expires: int) -> str:
    payload = f"{filename}:{expires}".encode("utf-8")
    return hmac.new(_upload_signing_secret(), payload, hashlib.sha256).hexdigest()


def _verify_upload_token(filename: str, expires: int, token: str) -> None:
    if expires < int(time.time()):
        raise HTTPException(status_code=403, detail="Upload link expired.")
    expected = _sign_upload(filename, expires)
    if not hmac.compare_digest(expected, token or ""):
        raise HTTPException(status_code=403, detail="Invalid upload link.")


def _build_upload_url(stored_name: str) -> str:
    expires = int(time.time()) + UPLOAD_LINK_TTL_SECONDS
    query = urlencode({"expires": str(expires), "token": _sign_upload(stored_name, expires)})
    proof_url = f"/uploads/{stored_name}?{query}"
    if WEB_APP_URL:
        proof_url = f"{WEB_APP_URL}{proof_url}"
    return proof_url


def _is_upload_file(value: Any) -> bool:
    return isinstance(value, (UploadFile, StarletteUploadFile))


async def _store_upload_file(file: StarletteUploadFile, *, label: str, allow_pdf: bool) -> Tuple[str, str]:
    mime = (file.content_type or "").lower()
    if allow_pdf:
        if mime not in {"image/jpeg", "image/png", "application/pdf"}:
            raise HTTPException(status_code=400, detail=f"Only JPG, PNG, or PDF is accepted for {label}.")
    elif mime not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=400, detail=f"Only JPG or PNG is accepted for {label}.")

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Uploaded {label} is empty.")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File is too large. Max allowed size is {UPLOAD_MAX_MB:.1f} MB.",
            )
    finally:
        await file.close()

    actual_mime = _detect_upload_mime(content)
    if allow_pdf:
        allowed_actual = {"image/jpeg", "image/png", "application/pdf"}
    else:
        allowed_actual = {"image/jpeg", "image/png"}
    if actual_mime not in allowed_actual:
        raise HTTPException(status_code=400, detail=f"Uploaded {label} is not a valid JPG, PNG, or PDF.")
    if actual_mime != mime:
        raise HTTPException(status_code=400, detail=f"Uploaded {label} type does not match the file content.")

    suffix = { "application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg" }[actual_mime]
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = Path(UPLOAD_DIR) / stored_name
    try:
        stored_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(status_code=507, detail=f"Upload storage error: {exc}") from exc
    return _build_upload_url(stored_name), "external"


def _detect_upload_mime(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return ""


def _client_rate_key(request: Request, scope: str, tg_id: Optional[int] = None) -> Tuple[str, str]:
    if tg_id is not None:
        return scope, f"tg:{tg_id}"
    forwarded = request.headers.get("x-forwarded-for", "")
    host = forwarded.split(",", 1)[0].strip()
    if not host and request.client:
        host = request.client.host
    return scope, host or "unknown"


def _enforce_rate_limit(request: Request, scope: str, limit: int, tg_id: Optional[int] = None) -> None:
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    key = _client_rate_key(request, scope, tg_id)
    bucket = [ts for ts in _RATE_LIMIT_BUCKETS.get(key, []) if ts >= cutoff]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Try again shortly.")
    bucket.append(now)
    _RATE_LIMIT_BUCKETS[key] = bucket


def _safe_upload_path(filename: str) -> Path:
    clean_name = Path(unquote(filename or "")).name
    if not clean_name or clean_name != filename or clean_name in {".", ".."}:
        raise HTTPException(status_code=404, detail="Upload not found.")
    file_path = (Path(UPLOAD_DIR) / clean_name).resolve()
    upload_root = Path(UPLOAD_DIR).resolve()
    if upload_root not in file_path.parents:
        raise HTTPException(status_code=404, detail="Upload not found.")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Upload not found.")
    return file_path


def _pending_status(status: str) -> bool:
    normalized = (status or "").strip().lower()
    return normalized in {
        STATUS_PENDING,
        "pending",
        "pending_payment",
        "pending_review",
        "pending_payment_approval",
    }


def cleanup_upload_storage(now_ts: Optional[float] = None) -> Dict[str, int]:
    upload_root = Path(UPLOAD_DIR)
    upload_root.mkdir(parents=True, exist_ok=True)
    now = float(now_ts if now_ts is not None else time.time())
    retention_seconds = UPLOAD_RETENTION_DAYS * 24 * 60 * 60

    referenced_any = set()
    referenced_pending = set()
    for row in [*db.list_external_payment_files(), *db.list_external_repost_files()]:
        filename = _extract_upload_filename(row["payment_file_id"])
        if not filename:
            continue
        referenced_any.add(filename)
        if _pending_status(row["status"]):
            referenced_pending.add(filename)

    scanned = 0
    deleted = 0
    kept = 0
    for file_path in upload_root.iterdir():
        if not file_path.is_file():
            continue
        scanned += 1
        filename = file_path.name
        if filename in referenced_pending:
            kept += 1
            continue

        orphan = filename not in referenced_any
        old = False
        if retention_seconds > 0:
            try:
                old = (now - file_path.stat().st_mtime) > retention_seconds
            except OSError:
                old = False

        if not (orphan or old):
            kept += 1
            continue

        try:
            file_path.unlink()
            deleted += 1
        except OSError:
            kept += 1

    return {
        "scanned": scanned,
        "deleted": deleted,
        "kept": kept,
        "referenced": len(referenced_any),
    }


def _maybe_run_upload_cleanup(force: bool = False) -> None:
    global _LAST_UPLOAD_CLEANUP_TS
    now = time.time()
    if not force and (now - _LAST_UPLOAD_CLEANUP_TS) < UPLOAD_CLEANUP_INTERVAL_SECONDS:
        return
    _LAST_UPLOAD_CLEANUP_TS = now
    try:
        cleanup_upload_storage(now_ts=now)
    except Exception:
        # Never break user flow because of cleanup issues.
        return


@app.on_event("startup")
def startup_cleanup() -> None:
    _maybe_run_upload_cleanup(force=True)


def _event_payload(event) -> Dict[str, Any]:
    tier = db.active_tier(event)
    payment_options = []
    for idx in (1, 2, 3):
        title = (getattr(event, f"payment{idx}_title", "") or "").strip()
        url = (getattr(event, f"payment{idx}_url", "") or "").strip()
        if not url:
            continue
        payment_options.append(
            {
                "slot": idx,
                "title": title or f"Payment Option {idx}",
                "url": url,
            }
        )
    return {
        "id": event.id,
        "title": event.title,
        "event_datetime": event.event_datetime,
        "location": event.location,
        "caption": event.caption,
        "photo_file_id": event.photo_file_id,
        "repost_discount_enabled": event.repost_discount_enabled,
        "repost_discount_amount": event.repost_discount_amount,
        "girls_group_offer_enabled": event.girls_group_offer_enabled,
        "boys_group_offer_enabled": event.boys_group_offer_enabled,
        "tier": tier,
        "payment_options": payment_options,
        "payment": {
            "payment1_title": (event.payment1_title or "").strip(),
            "payment1_url": (event.payment1_url or "").strip(),
            "payment2_title": (event.payment2_title or "").strip(),
            "payment2_url": (event.payment2_url or "").strip(),
            "payment3_title": (event.payment3_title or "").strip(),
            "payment3_url": (event.payment3_url or "").strip(),
        },
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
    repost_lines = "\n".join(
        [
            f"- {row['full_name']}: {row['repost_proof_file_id']}"
            for row in attendees
            if int(row["repost_discount_applied"] or 0) == 1 and (row["repost_proof_file_id"] or "").strip()
        ]
    ) or "-"
    event_title = event.title if event else f"Event #{reservation.event_id}"
    tier_label = _tier_label(reservation.ticket_type)
    buyer = "Unknown"
    if user:
        buyer = f"{user.name} {user.surname} (tg:{user.tg_id})"
    applied_discount_amount = max(float(reservation.group_discount_amount or 0.0), float(reservation.discount_amount or 0.0))

    caption = (
        "New payment proof pending review\n\n"
        f"Code: {reservation.code}\n"
        f"Event: {event_title}\n"
        f"Tier: {tier_label}\n"
        f"Boys: {reservation.boys} | Girls: {reservation.girls}\n"
        f"Base total: {reservation.base_total_price:.2f}\n"
        f"Girls 2+1 discount: {reservation.girls_group_free_count} free = {reservation.girls_group_discount_amount:.2f}\n"
        f"Boys 3+1 discount: {reservation.boys_group_free_count} free = {reservation.boys_group_discount_amount:.2f}\n"
        f"Group offer discount total: {reservation.group_discount_amount:.2f}\n"
        f"Repost discount: {reservation.discount_count} x {reservation.discount_unit_amount:.2f} = {reservation.discount_amount:.2f}\n"
        f"Applied discount: {applied_discount_amount:.2f}\n"
        f"Final total: {reservation.total_price:.2f}\n"
        f"Buyer: {buyer}\n\n"
        f"Attendees:\n{attendee_lines}\n\n"
        f"Payment proof: {reservation.payment_file_id}\n\n"
        f"Repost proofs:\n{repost_lines}"
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
            "text": (
                "Your booking is pending admin approval.\n"
                f"Code: {reservation.code}\n\n"
                "Please wait while we verify your payment proof.\n"
                "Approval usually takes from 5 minutes up to 6 hours.\n"
                "If it takes longer, contact us directly on Telegram: @budapest_tunderi"
            ),
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


class AdminEventDeleteRequest(BaseModel):
    tg_id: int
    event_id: int


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
    repost_discount_enabled: bool = False
    repost_discount_amount: float = Field(default=0, ge=0)
    girls_group_offer_enabled: bool = False
    boys_group_offer_enabled: bool = False
    payment1_title: str = ""
    payment1_url: str = ""
    payment2_title: str = ""
    payment2_url: str = ""
    payment3_title: str = ""
    payment3_url: str = ""
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
def admin_page() -> RedirectResponse:
    return RedirectResponse(url="/?open_admin=1", status_code=307)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/uploads/{filename}")
def signed_upload(filename: str, expires: int, token: str) -> FileResponse:
    _verify_upload_token(filename, expires, token)
    file_path = _safe_upload_path(filename)
    suffix = file_path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": f'inline; filename="{file_path.name}"',
        },
    )


@app.get("/api/events")
def list_events() -> Dict[str, Any]:
    items = []
    for event in db.list_events():
        payload = _event_payload(event)
        if payload["tier"]:
            items.append(payload)
    return {"items": items}


@app.get("/api/me")
def me(request: Request, tg_id: int) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, tg_id)
    user = db.get_user(verified_tg_id)
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
def my_tickets(request: Request, tg_id: int, limit: int = 20) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, tg_id)
    user = db.get_user(verified_tg_id)
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
async def book_with_payment(request: Request) -> Dict[str, Any]:
    _maybe_run_upload_cleanup()
    form = await request.form()
    upload_values = [value for _, value in form.multi_items() if _is_upload_file(value)]
    try:
        try:
            tg_id = int(str(form.get("tg_id", "")).strip())
            event_id = int(str(form.get("event_id", "")).strip())
            boys = int(str(form.get("boys", "")).strip())
            girls = int(str(form.get("girls", "")).strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="tg_id, event_id, boys, and girls must be integers.") from exc
        tg_id = _request_tg_id(request, tg_id)
        _enforce_rate_limit(request, "booking", BOOKING_RATE_LIMIT, tg_id)
        attendees = str(form.get("attendees", ""))
        payment_file = form.get("file")
        if not _is_upload_file(payment_file):
            raise HTTPException(status_code=400, detail="Payment proof file is required.")

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

        event = db.get_event(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        discounted_indexes_raw = str(form.get("discounted_attendee_indexes", "[]"))
        try:
            discounted_indexes_payload = json.loads(discounted_indexes_raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="discounted_attendee_indexes must be valid JSON list.") from exc
        if not isinstance(discounted_indexes_payload, list):
            raise HTTPException(status_code=400, detail="discounted_attendee_indexes must be a list.")
        try:
            discounted_indexes = sorted({int(idx) for idx in discounted_indexes_payload})
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="discounted_attendee_indexes must contain integers.") from exc
        if any(idx < 0 or idx >= len(normalized_attendees) for idx in discounted_indexes):
            raise HTTPException(status_code=400, detail="Discounted attendee indexes are out of range.")
        if discounted_indexes and not bool(event.repost_discount_enabled):
            raise HTTPException(status_code=400, detail="Repost discount is not enabled for this event.")

        repost_proofs_by_index: Dict[int, Tuple[str, str]] = {}
        for idx in discounted_indexes:
            repost_file = form.get(f"repost_file_{idx}")
            if not _is_upload_file(repost_file):
                raise HTTPException(status_code=400, detail="Upload repost screenshot for each selected attendee.")
            repost_proofs_by_index[idx] = await _store_upload_file(
                repost_file,
                label=f"repost screenshot for attendee #{idx + 1}",
                allow_pdf=False,
            )

        proof_url, proof_type = await _store_upload_file(
            payment_file,
            label="payment proof",
            allow_pdf=True,
        )

        try:
            reservation = db.create_pending_reservation(
                user_id=user.id,
                event_id=int(event_id),
                boys=int(boys),
                girls=int(girls),
                attendees=normalized_attendees,
                payment_file_id=proof_url,
                payment_file_type=proof_type,
                discounted_attendee_indexes=discounted_indexes,
                repost_proofs_by_index=repost_proofs_by_index,
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
    finally:
        for upload in upload_values:
            try:
                await upload.close()
            except Exception:
                continue


@app.post("/api/quote")
def quote(request: Request, payload: QuoteRequest) -> Dict[str, Any]:
    _enforce_rate_limit(request, "quote", QUOTE_RATE_LIMIT)
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
def admin_bootstrap(request: Request, tg_id: int) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, tg_id)
    _require_admin(verified_tg_id)
    return {"ok": True, "tg_id": verified_tg_id}


@app.get("/api/admin/guests")
def admin_guests(
    request: Request,
    tg_id: int,
    sort_by: str = "newest",
    search: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, tg_id)
    _require_admin(verified_tg_id)
    rows = db.list_guests(sort_by=sort_by, search=search, limit=limit)
    return {"items": [_row_dict(r) for r in rows]}


@app.get("/api/admin/reservations")
def admin_reservations(request: Request, tg_id: int, search: Optional[str] = None, limit: int = 25) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, tg_id)
    _require_admin(verified_tg_id)
    rows = db.list_active_reservations(search=search, limit=limit)
    return {"items": [_row_dict(r) for r in rows]}


@app.get("/api/admin/events")
def admin_events(request: Request, tg_id: int) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, tg_id)
    _require_admin(verified_tg_id)
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
            "repost_discount_enabled": event.repost_discount_enabled,
            "repost_discount_amount": event.repost_discount_amount,
            "girls_group_offer_enabled": event.girls_group_offer_enabled,
            "boys_group_offer_enabled": event.boys_group_offer_enabled,
        }
        items.append(payload)
    return {"items": items}


@app.post("/api/admin/guest/add")
def admin_guest_add(request: Request, payload: AdminGuestAddRequest) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, payload.tg_id)
    _require_admin(verified_tg_id)
    ok, message, reservation = db.admin_add_guest(
        reservation_code=payload.reservation_code.strip(),
        full_name=payload.full_name.strip(),
        gender_raw=payload.gender.strip().lower(),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "reservation": reservation.__dict__ if reservation else None}


@app.post("/api/admin/guest/remove")
def admin_guest_remove(request: Request, payload: AdminGuestRemoveRequest) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, payload.tg_id)
    _require_admin(verified_tg_id)
    ok, message, reservation = db.admin_remove_guest(payload.attendee_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "reservation": reservation.__dict__ if reservation else None}


@app.post("/api/admin/guest/rename")
def admin_guest_rename(request: Request, payload: AdminGuestRenameRequest) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, payload.tg_id)
    _require_admin(verified_tg_id)
    ok, message = db.admin_rename_guest(payload.attendee_id, payload.full_name.strip())
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message}


@app.post("/api/admin/guest/add_by_event")
def admin_guest_add_by_event(request: Request, payload: AdminGuestAddByEventRequest) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, payload.tg_id)
    _require_admin(verified_tg_id)
    ok, message, reservation = db.admin_add_guest_by_event(
        admin_tg_id=verified_tg_id,
        event_id=payload.event_id,
        name=payload.name.strip(),
        surname=payload.surname.strip(),
        gender_raw=payload.gender.strip().lower(),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "reservation": reservation.__dict__ if reservation else None}


@app.post("/api/admin/guest/remove_by_name")
def admin_guest_remove_by_name(request: Request, payload: AdminGuestRemoveByNameRequest) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, payload.tg_id)
    _require_admin(verified_tg_id)
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
    request: Request,
    tg_id: int = Form(...),
    event_id: int = Form(...),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, tg_id)
    _require_admin(verified_tg_id)
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Upload .xlsx file.")

    try:
        raw = await file.read()
    finally:
        await file.close()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Max allowed size is {UPLOAD_MAX_MB:.1f} MB.",
        )
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

        ok, message, _reservation = db.admin_import_guest_by_event(
            admin_tg_id=verified_tg_id,
            event_id=event_id,
            name=value_name,
            surname=value_surname,
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
def admin_guest_export_xlsx(request: Request, tg_id: int) -> StreamingResponse:
    verified_tg_id = _request_tg_id(request, tg_id)
    _require_admin(verified_tg_id)
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
def admin_event_update(request: Request, payload: AdminEventUpdateRequest) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, payload.tg_id)
    _require_admin(verified_tg_id)
    ok, message = db.set_event_fields(event_id=payload.event_id, updates=payload.updates)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    event = db.get_event(payload.event_id)
    return {"ok": True, "message": message, "event": event.__dict__ if event else None}


@app.post("/api/admin/event/delete")
def admin_event_delete(request: Request, payload: AdminEventDeleteRequest) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, payload.tg_id)
    _require_admin(verified_tg_id)
    ok, message, deleted = db.delete_event(event_id=payload.event_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "deleted": deleted}


@app.post("/api/admin/event/create_simple")
def admin_event_create_simple(request: Request, payload: AdminEventCreateSimpleRequest) -> Dict[str, Any]:
    verified_tg_id = _request_tg_id(request, payload.tg_id)
    _require_admin(verified_tg_id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required.")

    payment_fields = {
        "payment1_url": payload.payment1_url,
        "payment2_url": payload.payment2_url,
        "payment3_url": payload.payment3_url,
    }
    for field_name, field_value in payment_fields.items():
        cleaned = (field_value or "").strip()
        if cleaned and not cleaned.lower().startswith("https://"):
            raise HTTPException(status_code=400, detail=f"{field_name} must start with https://")

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
        repost_discount_enabled=bool(payload.repost_discount_enabled),
        repost_discount_amount=float(payload.repost_discount_amount),
        girls_group_offer_enabled=bool(payload.girls_group_offer_enabled),
        boys_group_offer_enabled=bool(payload.boys_group_offer_enabled),
        payment1_title=(payload.payment1_title or "").strip(),
        payment1_url=(payload.payment1_url or "").strip(),
        payment2_title=(payload.payment2_title or "").strip(),
        payment2_url=(payload.payment2_url or "").strip(),
        payment3_title=(payload.payment3_title or "").strip(),
        payment3_url=(payload.payment3_url or "").strip(),
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
