import os
from pathlib import Path
from typing import Any, Dict

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


@app.get("/")
def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


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


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("MINI_APP_HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("MINI_APP_PORT", "8080"))
    reload_enabled = os.getenv("MINI_APP_RELOAD", "0") == "1"
    uvicorn.run("ticketbot.miniapp_server:app", host=host, port=port, reload=reload_enabled)
