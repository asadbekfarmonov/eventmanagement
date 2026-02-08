from dataclasses import dataclass
from typing import List, Optional

from ticketbot.database import Database
from ticketbot.models import Event, Reservation, User


@dataclass
class ReservationRequest:
    user_id: int
    event_id: int
    ticket_type: str
    quantity: int
    price_per_ticket: float
    boys: int
    girls: int
    attendees: List[dict]


class UserService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, tg_id: int, name: str, surname: str, phone: str) -> None:
        self.db.upsert_user(tg_id, name, surname, phone)

    def get(self, tg_id: int) -> Optional[User]:
        return self.db.get_user(tg_id)

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
        early_bird_price: float,
        regular_price: float,
        early_bird_qty: int,
        capacity: Optional[int],
    ) -> int:
        return self.db.create_event(
            title=title,
            event_datetime=event_datetime,
            location=location,
            early_bird_price=early_bird_price,
            regular_price=regular_price,
            early_bird_qty=early_bird_qty,
            capacity=capacity,
        )


class ReservationService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, request: ReservationRequest) -> Reservation:
        return self.db.reserve_event(
            user_id=request.user_id,
            event_id=request.event_id,
            ticket_type=request.ticket_type,
            quantity=request.quantity,
            price_per_ticket=request.price_per_ticket,
            boys=request.boys,
            girls=request.girls,
            attendees=request.attendees,
        )

    def list_for_user(self, user_id: int) -> List[Reservation]:
        return self.db.list_reservations_for_user(user_id)

    def cancel(self, reservation_id: int) -> None:
        self.db.cancel_reservation(reservation_id)


class AdminService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_blocked_users(self):
        return self.db.list_blocked_users()

    def export_event_csv(self, event_id: int) -> List[List[str]]:
        return self.db.export_event_csv(event_id)
