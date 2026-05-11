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
    repost_discount_enabled: int = 0
    repost_discount_amount: float = 0.0
    girls_group_offer_enabled: int = 0
    boys_group_offer_enabled: int = 0
    payment1_title: str = ""
    payment1_url: str = ""
    payment2_title: str = ""
    payment2_url: str = ""
    payment3_title: str = ""
    payment3_url: str = ""


@dataclass
class Reservation:
    id: int
    code: str
    user_id: int
    event_id: int
    ticket_type: str
    quantity: int
    total_price: float
    base_total_price: float
    girls_group_free_count: int
    boys_group_free_count: int
    girls_group_discount_amount: float
    boys_group_discount_amount: float
    group_discount_amount: float
    discount_count: int
    discount_unit_amount: float
    discount_amount: float
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
