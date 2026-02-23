from dataclasses import dataclass
from typing import List, Optional, Tuple

from ticketbot.database import Database
from ticketbot.models import Event, Reservation, User


@dataclass
class ActionResult:
    success: bool
    message: str
    reservation: Optional[Reservation] = None


class UserService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, tg_id: int, name: str, surname: str, phone: str) -> None:
        self.db.upsert_user(tg_id, name, surname, phone)

    def get(self, tg_id: int) -> Optional[User]:
        return self.db.get_user(tg_id)

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.get_user_by_id(user_id)

    def is_blocked(self, tg_id: int) -> bool:
        return self.db.is_blocked(tg_id)


class EventService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_open(self) -> List[Event]:
        return self.db.list_events()

    def get(self, event_id: int) -> Optional[Event]:
        return self.db.get_event(event_id)

    def create(
        self,
        title: str,
        event_datetime: str,
        location: str,
        caption: str,
        photo_file_id: str,
        early_boy_price: float,
        early_girl_price: float,
        early_qty: int,
        tier1_boy_price: float,
        tier1_girl_price: float,
        tier1_qty: int,
        tier2_boy_price: float,
        tier2_girl_price: float,
        tier2_qty: int,
    ) -> int:
        self.db.parse_event_datetime(event_datetime)
        return self.db.create_event(
            title=title,
            event_datetime=event_datetime,
            location=location,
            caption=caption,
            photo_file_id=photo_file_id,
            early_boy_price=early_boy_price,
            early_girl_price=early_girl_price,
            early_qty=early_qty,
            tier1_boy_price=tier1_boy_price,
            tier1_girl_price=tier1_girl_price,
            tier1_qty=tier1_qty,
            tier2_boy_price=tier2_boy_price,
            tier2_girl_price=tier2_girl_price,
            tier2_qty=tier2_qty,
        )

    def active_tier(self, event: Event):
        return self.db.active_tier(event)

    def total_remaining(self, event: Event) -> int:
        return self.db.total_remaining(event)


class ReservationService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_pending(
        self,
        user_id: int,
        event_id: int,
        boys: int,
        girls: int,
        attendees: List[str],
        payment_file_id: str,
        payment_file_type: str,
    ) -> Reservation:
        return self.db.create_pending_reservation(
            user_id=user_id,
            event_id=event_id,
            boys=boys,
            girls=girls,
            attendees=attendees,
            payment_file_id=payment_file_id,
            payment_file_type=payment_file_type,
        )

    def list_for_user(self, user_id: int) -> List[Reservation]:
        return self.db.list_reservations_for_user(user_id)

    def get_by_code(self, code: str) -> Optional[Reservation]:
        return self.db.get_reservation_by_code(code)

    def get_by_id(self, reservation_id: int) -> Optional[Reservation]:
        try:
            return self.db.get_reservation(reservation_id)
        except Exception:
            return None

    def list_attendees(self, reservation_id: int) -> List[str]:
        return [row["full_name"] for row in self.db.list_attendees(reservation_id)]

    def cancel_by_code(self, user_id: int, reservation_code: str) -> ActionResult:
        ok, message, reservation = self.db.cancel_reservation_for_user(user_id, reservation_code)
        return ActionResult(ok, message, reservation)

    def approve_by_admin(self, reservation_id: int, admin_tg_id: int) -> ActionResult:
        ok, message, reservation = self.db.approve_reservation(reservation_id, admin_tg_id)
        return ActionResult(ok, message, reservation)

    def reject_by_admin(self, reservation_id: int, admin_tg_id: int, note: str) -> ActionResult:
        ok, message, reservation = self.db.reject_reservation(reservation_id, admin_tg_id, note)
        return ActionResult(ok, message, reservation)


class AdminService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_blocked_users(self):
        return self.db.list_blocked_users()

    def export_event_csv(self, event_id: int) -> List[List[str]]:
        return self.db.export_event_csv(event_id)

    def set_event_price(self, event_id: int, price_field: str, value: float) -> bool:
        return self.db.set_event_price(event_id, price_field, value)

    def list_event_stats(
        self,
        sort_by: str = "date",
        search: Optional[str] = None,
        limit: int = 30,
    ):
        return self.db.list_event_stats(sort_by=sort_by, search=search, limit=limit)

    def search_reservations(
        self,
        query_text: str,
        sort_by: str = "newest",
        limit: int = 20,
    ):
        return self.db.search_reservations(query_text=query_text, sort_by=sort_by, limit=limit)

    def list_guests(
        self,
        sort_by: str = "newest",
        search: Optional[str] = None,
        limit: int = 25,
    ):
        return self.db.list_guests(sort_by=sort_by, search=search, limit=limit)

    def add_guest(self, reservation_code: str, full_name: str, gender: str) -> ActionResult:
        ok, message, reservation = self.db.admin_add_guest(reservation_code, full_name, gender)
        return ActionResult(ok, message, reservation)

    def remove_guest(self, attendee_id: int) -> ActionResult:
        ok, message, reservation = self.db.admin_remove_guest(attendee_id)
        return ActionResult(ok, message, reservation)

    def rename_guest(self, attendee_id: int, full_name: str) -> ActionResult:
        ok, message = self.db.admin_rename_guest(attendee_id, full_name)
        return ActionResult(ok, message, None)

    def set_event_fields(self, event_id: int, updates: dict) -> Tuple[bool, str]:
        return self.db.set_event_fields(event_id, updates)

    def price_field_labels(self) -> List[Tuple[str, str]]:
        return [
            ("early_boy", "Early Boys"),
            ("early_girl", "Early Girls"),
            ("tier1_boy", "Tier-1 Boys"),
            ("tier1_girl", "Tier-1 Girls"),
            ("tier2_boy", "Tier-2 Boys"),
            ("tier2_girl", "Tier-2 Girls"),
        ]
