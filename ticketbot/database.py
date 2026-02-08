import os
import sqlite3
from datetime import datetime
from typing import List, Optional

from ticketbot.models import Event, Reservation, User


class Database:
    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                phone TEXT NOT NULL,
                blocked INTEGER DEFAULT 0,
                blocked_reason TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_datetime TEXT NOT NULL,
                location TEXT NOT NULL,
                early_bird_price REAL NOT NULL,
                regular_price REAL NOT NULL,
                early_bird_qty INTEGER NOT NULL,
                capacity INTEGER,
                status TEXT NOT NULL DEFAULT 'open'
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                ticket_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price_per_ticket REAL NOT NULL,
                total_price REAL NOT NULL,
                boys INTEGER NOT NULL,
                girls INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'reserved',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (event_id) REFERENCES events(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'reserved',
                FOREIGN KEY (reservation_id) REFERENCES reservations(id)
            )
            """
        )
        self.conn.commit()

    def upsert_user(self, tg_id: int, name: str, surname: str, phone: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (tg_id, name, surname, phone)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                name=excluded.name,
                surname=excluded.surname,
                phone=excluded.phone
            """,
            (tg_id, name, surname, phone),
        )
        self.conn.commit()

    def get_user(self, tg_id: int) -> Optional[User]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        row = cursor.fetchone()
        return User(**dict(row)) if row else None

    def is_blocked(self, tg_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT blocked FROM users WHERE tg_id = ?", (tg_id,))
        row = cursor.fetchone()
        return bool(row["blocked"]) if row else False

    def list_events(self) -> List[Event]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM events WHERE status = 'open' ORDER BY event_datetime")
        return [Event(**dict(row)) for row in cursor.fetchall()]

    def get_event(self, event_id: int) -> Optional[Event]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        return Event(**dict(row)) if row else None

    def create_event(
        self,
        title: str,
        event_datetime: str,
        location: str,
        early_bird_price: float,
        regular_price: float,
        early_bird_qty: int,
        capacity: Optional[int],
    ) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO events (title, event_datetime, location, early_bird_price, regular_price, early_bird_qty, capacity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                event_datetime,
                location,
                early_bird_price,
                regular_price,
                early_bird_qty,
                capacity,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def reserve_event(
        self,
        user_id: int,
        event_id: int,
        ticket_type: str,
        quantity: int,
        price_per_ticket: float,
        boys: int,
        girls: int,
        attendees: List[dict],
    ) -> Reservation:
        total_price = price_per_ticket * quantity
        code = f"R{event_id}{int(datetime.utcnow().timestamp())}{user_id}"
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO reservations (code, user_id, event_id, ticket_type, quantity, price_per_ticket, total_price, boys, girls, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code,
                user_id,
                event_id,
                ticket_type,
                quantity,
                price_per_ticket,
                total_price,
                boys,
                girls,
                datetime.utcnow().isoformat(),
            ),
        )
        reservation_id = cursor.lastrowid
        for attendee in attendees:
            cursor.execute(
                """
                INSERT INTO attendees (reservation_id, name, surname)
                VALUES (?, ?, ?)
                """,
                (reservation_id, attendee["name"], attendee["surname"]),
            )
        if ticket_type == "early" and quantity > 0:
            cursor.execute(
                """
                UPDATE events SET early_bird_qty = early_bird_qty - ?
                WHERE id = ?
                """,
                (quantity, event_id),
            )
        self.conn.commit()
        return self.get_reservation(reservation_id)

    def get_reservation(self, reservation_id: int) -> Reservation:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
        row = cursor.fetchone()
        return Reservation(**dict(row))

    def list_reservations_for_user(self, user_id: int) -> List[Reservation]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM reservations
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [Reservation(**dict(row)) for row in cursor.fetchall()]

    def list_attendees(self, reservation_id: int) -> List[sqlite3.Row]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM attendees WHERE reservation_id = ?", (reservation_id,))
        return cursor.fetchall()

    def cancel_reservation(self, reservation_id: int) -> None:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
        reservation = cursor.fetchone()
        if not reservation:
            return
        cursor.execute(
            """
            UPDATE reservations SET status = 'cancelled' WHERE id = ?
            """,
            (reservation_id,),
        )
        if reservation["ticket_type"] == "early":
            cursor.execute(
                """
                UPDATE events SET early_bird_qty = early_bird_qty + ? WHERE id = ?
                """,
                (reservation["quantity"], reservation["event_id"]),
            )
        self.conn.commit()

    def list_guest_list(self, event_id: int) -> List[sqlite3.Row]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT r.*, u.name AS buyer_name, u.surname AS buyer_surname, u.phone
            FROM reservations r
            JOIN users u ON r.user_id = u.id
            WHERE r.event_id = ?
            ORDER BY r.created_at
            """,
            (event_id,),
        )
        return cursor.fetchall()

    def mark_entered(self, reservation_id: int) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE reservations SET status = 'entered' WHERE id = ?
            """,
            (reservation_id,),
        )
        cursor.execute(
            """
            UPDATE attendees SET status = 'entered' WHERE reservation_id = ?
            """,
            (reservation_id,),
        )
        self.conn.commit()

    def set_blocked(self, tg_id: int, blocked: bool, reason: Optional[str] = None) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE users SET blocked = ?, blocked_reason = ? WHERE tg_id = ?
            """,
            (1 if blocked else 0, reason, tg_id),
        )
        self.conn.commit()

    def list_blocked_users(self) -> List[sqlite3.Row]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE blocked = 1")
        return cursor.fetchall()

    def export_event_csv(self, event_id: int) -> List[List[str]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT r.code, r.ticket_type, r.price_per_ticket, r.total_price, r.boys, r.girls, r.status,
                   u.name, u.surname, u.phone
            FROM reservations r
            JOIN users u ON r.user_id = u.id
            WHERE r.event_id = ?
            """,
            (event_id,),
        )
        rows = []
        for row in cursor.fetchall():
            rows.append(
                [
                    row["code"],
                    row["ticket_type"],
                    str(row["price_per_ticket"]),
                    str(row["total_price"]),
                    str(row["boys"]),
                    str(row["girls"]),
                    row["status"],
                    row["name"],
                    row["surname"],
                    row["phone"],
                ]
            )
        return rows
