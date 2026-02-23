from dataclasses import dataclass
from typing import Optional


@dataclass
class Event:
    id: int
    title: str
    event_datetime: str
    location: str
    caption: str
    photo_file_id: str
    early_bird_price: float
    early_bird_price_girl: float
    early_bird_qty: int
    regular_tier1_price: float
    regular_tier1_price_girl: float
    regular_tier1_qty: int
    regular_tier2_price: float
    regular_tier2_price_girl: float
    regular_tier2_qty: int
    status: str


@dataclass
class Reservation:
    id: int
    code: str
    user_id: int
    event_id: int
    ticket_type: str
    quantity: int
    total_price: float
    boys: int
    girls: int
    status: str
    created_at: str
    payment_file_id: str
    payment_file_type: str
    admin_note: str
    reviewed_at: Optional[str]
    reviewed_by_tg_id: Optional[int]
    hold_applied: int


@dataclass
class User:
    id: int
    tg_id: int
    name: str
    surname: str
    phone: str
    blocked: int
    blocked_reason: Optional[str]
