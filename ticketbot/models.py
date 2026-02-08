from dataclasses import dataclass
from typing import Optional


@dataclass
class Event:
    id: int
    title: str
    event_datetime: str
    location: str
    early_bird_price: float
    regular_price: float
    early_bird_qty: int
    capacity: Optional[int]
    status: str


@dataclass
class Reservation:
    id: int
    code: str
    user_id: int
    event_id: int
    ticket_type: str
    quantity: int
    price_per_ticket: float
    total_price: float
    boys: int
    girls: int
    status: str
    created_at: str


@dataclass
class User:
    id: int
    tg_id: int
    name: str
    surname: str
    phone: str
    blocked: int
    blocked_reason: Optional[str]
