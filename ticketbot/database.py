import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from ticketbot.models import Event, Reservation, User

EVENT_DT_FORMAT = "%Y-%m-%d %H:%M"
BUDAPEST_TZ = ZoneInfo("Europe/Budapest")

STATUS_PENDING = "pending_payment_review"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"


class Database:
    def __init__(self, path: str) -> None:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self._init_schema()
        self._migrate_schema()

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
                caption TEXT NOT NULL DEFAULT '',
                photo_file_id TEXT NOT NULL DEFAULT '',
                early_bird_price REAL NOT NULL,
                early_bird_price_girl REAL NOT NULL DEFAULT 0,
                early_bird_qty INTEGER NOT NULL,
                regular_tier1_price REAL NOT NULL DEFAULT 0,
                regular_tier1_price_girl REAL NOT NULL DEFAULT 0,
                regular_tier1_qty INTEGER NOT NULL DEFAULT 0,
                regular_tier2_price REAL NOT NULL DEFAULT 0,
                regular_tier2_price_girl REAL NOT NULL DEFAULT 0,
                regular_tier2_qty INTEGER NOT NULL DEFAULT 0,
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
                total_price REAL NOT NULL,
                boys INTEGER NOT NULL,
                girls INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_payment_review',
                created_at TEXT NOT NULL,
                payment_file_id TEXT NOT NULL DEFAULT '',
                payment_file_type TEXT NOT NULL DEFAULT '',
                admin_note TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT,
                reviewed_by_tg_id INTEGER,
                hold_applied INTEGER NOT NULL DEFAULT 1,
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
                full_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'reserved',
                FOREIGN KEY (reservation_id) REFERENCES reservations(id)
            )
            """
        )
        self.conn.commit()

    def _migrate_schema(self) -> None:
        cursor = self.conn.cursor()

        event_cols = self._table_columns("events")
        if "caption" not in event_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN caption TEXT NOT NULL DEFAULT ''")
        if "photo_file_id" not in event_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN photo_file_id TEXT NOT NULL DEFAULT ''")

        if "regular_tier1_price" not in event_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN regular_tier1_price REAL NOT NULL DEFAULT 0")
            if "regular_price" in event_cols:
                cursor.execute("UPDATE events SET regular_tier1_price = regular_price")
        if "regular_tier1_qty" not in event_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN regular_tier1_qty INTEGER NOT NULL DEFAULT 0")
        if "regular_tier2_price" not in event_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN regular_tier2_price REAL NOT NULL DEFAULT 0")
        if "regular_tier2_qty" not in event_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN regular_tier2_qty INTEGER NOT NULL DEFAULT 0")

        if "early_bird_price_girl" not in event_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN early_bird_price_girl REAL NOT NULL DEFAULT 0")
            cursor.execute("UPDATE events SET early_bird_price_girl = early_bird_price")
        if "regular_tier1_price_girl" not in event_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN regular_tier1_price_girl REAL NOT NULL DEFAULT 0")
            cursor.execute("UPDATE events SET regular_tier1_price_girl = regular_tier1_price")
        if "regular_tier2_price_girl" not in event_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN regular_tier2_price_girl REAL NOT NULL DEFAULT 0")
            cursor.execute("UPDATE events SET regular_tier2_price_girl = regular_tier2_price")

        reservation_cols = self._table_columns("reservations")
        if "payment_file_id" not in reservation_cols:
            cursor.execute("ALTER TABLE reservations ADD COLUMN payment_file_id TEXT NOT NULL DEFAULT ''")
        if "payment_file_type" not in reservation_cols:
            cursor.execute("ALTER TABLE reservations ADD COLUMN payment_file_type TEXT NOT NULL DEFAULT ''")
        if "admin_note" not in reservation_cols:
            cursor.execute("ALTER TABLE reservations ADD COLUMN admin_note TEXT NOT NULL DEFAULT ''")
        if "reviewed_at" not in reservation_cols:
            cursor.execute("ALTER TABLE reservations ADD COLUMN reviewed_at TEXT")
        if "reviewed_by_tg_id" not in reservation_cols:
            cursor.execute("ALTER TABLE reservations ADD COLUMN reviewed_by_tg_id INTEGER")
        if "hold_applied" not in reservation_cols:
            cursor.execute("ALTER TABLE reservations ADD COLUMN hold_applied INTEGER NOT NULL DEFAULT 1")

        cursor.execute("UPDATE reservations SET status = ? WHERE status = 'reserved'", (STATUS_APPROVED,))

        attendee_cols = self._table_columns("attendees")
        if "full_name" not in attendee_cols:
            cursor.execute("ALTER TABLE attendees ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
        cursor.execute(
            """
            UPDATE attendees
            SET full_name = TRIM(name || ' ' || COALESCE(surname, ''))
            WHERE full_name = ''
            """
        )

        self.conn.commit()

    def _table_columns(self, table_name: str) -> set:
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row["name"] for row in cursor.fetchall()}

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def parse_event_datetime(self, value: str) -> datetime:
        parsed = datetime.strptime(value, EVENT_DT_FORMAT)
        return parsed.replace(tzinfo=BUDAPEST_TZ)

    def _tier_qty_column(self, tier_key: str) -> str:
        mapping = {
            "early": "early_bird_qty",
            "tier1": "regular_tier1_qty",
            "tier2": "regular_tier2_qty",
        }
        if tier_key not in mapping:
            raise ValueError("Unknown ticket type")
        return mapping[tier_key]

    def _tier_prices(self, event: Event, tier_key: str) -> Tuple[float, float]:
        if tier_key == "early":
            return event.early_bird_price, event.early_bird_price_girl
        if tier_key == "tier1":
            return event.regular_tier1_price, event.regular_tier1_price_girl
        if tier_key == "tier2":
            return event.regular_tier2_price, event.regular_tier2_price_girl
        raise ValueError("Unknown ticket type")

    def _release_hold(self, reservation_row: sqlite3.Row, cursor: sqlite3.Cursor) -> None:
        if reservation_row["hold_applied"] != 1:
            return
        qty_column = self._tier_qty_column(reservation_row["ticket_type"])
        cursor.execute(
            f"UPDATE events SET {qty_column} = {qty_column} + ? WHERE id = ?",
            (reservation_row["quantity"], reservation_row["event_id"]),
        )

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

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return User(**dict(row)) if row else None

    def is_blocked(self, tg_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT blocked FROM users WHERE tg_id = ?", (tg_id,))
        row = cursor.fetchone()
        return bool(row["blocked"]) if row else False

    def list_events(self) -> List[Event]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, title, event_datetime, location, caption, photo_file_id,
                   early_bird_price, early_bird_price_girl, early_bird_qty,
                   regular_tier1_price, regular_tier1_price_girl, regular_tier1_qty,
                   regular_tier2_price, regular_tier2_price_girl, regular_tier2_qty,
                   status
            FROM events
            WHERE status = 'open'
            ORDER BY event_datetime
            """
        )
        return [Event(**dict(row)) for row in cursor.fetchall()]

    def get_event(self, event_id: int) -> Optional[Event]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, title, event_datetime, location, caption, photo_file_id,
                   early_bird_price, early_bird_price_girl, early_bird_qty,
                   regular_tier1_price, regular_tier1_price_girl, regular_tier1_qty,
                   regular_tier2_price, regular_tier2_price_girl, regular_tier2_qty,
                   status
            FROM events
            WHERE id = ?
            """,
            (event_id,),
        )
        row = cursor.fetchone()
        return Event(**dict(row)) if row else None

    def create_event(
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
        event_cols = self._table_columns("events")
        insert_values = {
            "title": title,
            "event_datetime": event_datetime,
            "location": location,
            "caption": caption,
            "photo_file_id": photo_file_id,
            "early_bird_price": early_boy_price,
            "early_bird_price_girl": early_girl_price,
            "early_bird_qty": early_qty,
            "regular_tier1_price": tier1_boy_price,
            "regular_tier1_price_girl": tier1_girl_price,
            "regular_tier1_qty": tier1_qty,
            "regular_tier2_price": tier2_boy_price,
            "regular_tier2_price_girl": tier2_girl_price,
            "regular_tier2_qty": tier2_qty,
            "status": "open",
        }

        # Backward compatibility for legacy schema variants.
        if "regular_price" in event_cols:
            insert_values["regular_price"] = tier1_boy_price
        if "capacity" in event_cols:
            insert_values["capacity"] = None

        columns = [col for col in insert_values.keys() if col in event_cols]
        placeholders = ", ".join(["?"] * len(columns))
        cursor = self.conn.cursor()
        cursor.execute(
            f"INSERT INTO events ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(insert_values[col] for col in columns),
        )
        self.conn.commit()
        return cursor.lastrowid

    def active_tier(self, event: Event) -> Optional[Dict[str, float]]:
        if event.early_bird_qty > 0:
            return {
                "key": "early",
                "name": "Early Bird",
                "boy_price": event.early_bird_price,
                "girl_price": event.early_bird_price_girl,
                "remaining": event.early_bird_qty,
            }
        if event.regular_tier1_qty > 0:
            return {
                "key": "tier1",
                "name": "Regular Tier-1",
                "boy_price": event.regular_tier1_price,
                "girl_price": event.regular_tier1_price_girl,
                "remaining": event.regular_tier1_qty,
            }
        if event.regular_tier2_qty > 0:
            return {
                "key": "tier2",
                "name": "Regular Tier-2",
                "boy_price": event.regular_tier2_price,
                "girl_price": event.regular_tier2_price_girl,
                "remaining": event.regular_tier2_qty,
            }
        return None

    def total_remaining(self, event: Event) -> int:
        return event.early_bird_qty + event.regular_tier1_qty + event.regular_tier2_qty

    def create_pending_reservation(
        self,
        user_id: int,
        event_id: int,
        boys: int,
        girls: int,
        attendees: List[str],
        payment_file_id: str,
        payment_file_type: str,
    ) -> Reservation:
        event = self.get_event(event_id)
        if not event:
            raise ValueError("Event not found")

        active_tier = self.active_tier(event)
        if not active_tier:
            raise ValueError("Event is sold out")

        quantity = boys + girls
        if quantity <= 0:
            raise ValueError("At least one attendee is required")
        if quantity > active_tier["remaining"]:
            raise ValueError("Not enough tickets in current tier")
        if len(attendees) != quantity:
            raise ValueError("Attendee count does not match boys + girls")

        total_price = boys * active_tier["boy_price"] + girls * active_tier["girl_price"]
        code = f"R{event_id}-{uuid.uuid4().hex[:8].upper()}"

        cursor = self.conn.cursor()
        reservation_cols = self._table_columns("reservations")
        avg_price = (total_price / quantity) if quantity > 0 else 0.0
        insert_values = {
            "code": code,
            "user_id": user_id,
            "event_id": event_id,
            "ticket_type": active_tier["key"],
            "quantity": quantity,
            "total_price": total_price,
            "boys": boys,
            "girls": girls,
            "status": STATUS_PENDING,
            "created_at": self._utc_now(),
        }

        if "price_per_ticket" in reservation_cols:
            insert_values["price_per_ticket"] = avg_price
        if "paid_tickets" in reservation_cols:
            insert_values["paid_tickets"] = quantity
        if "credit_used_tickets" in reservation_cols:
            insert_values["credit_used_tickets"] = 0
        if "credit_source_codes" in reservation_cols:
            insert_values["credit_source_codes"] = ""
        if "payment_file_id" in reservation_cols:
            insert_values["payment_file_id"] = payment_file_id
        if "payment_file_type" in reservation_cols:
            insert_values["payment_file_type"] = payment_file_type
        if "admin_note" in reservation_cols:
            insert_values["admin_note"] = ""
        if "reviewed_at" in reservation_cols:
            insert_values["reviewed_at"] = None
        if "reviewed_by_tg_id" in reservation_cols:
            insert_values["reviewed_by_tg_id"] = None
        if "hold_applied" in reservation_cols:
            insert_values["hold_applied"] = 1

        columns = list(insert_values.keys())
        placeholders = ", ".join(["?"] * len(columns))
        cursor.execute(
            f"INSERT INTO reservations ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(insert_values[column] for column in columns),
        )
        reservation_id = cursor.lastrowid

        for full_name in attendees:
            cursor.execute(
                """
                INSERT INTO attendees (reservation_id, name, surname, full_name)
                VALUES (?, ?, '', ?)
                """,
                (reservation_id, full_name, full_name),
            )

        qty_column = self._tier_qty_column(active_tier["key"])
        cursor.execute(
            f"UPDATE events SET {qty_column} = {qty_column} - ? WHERE id = ?",
            (quantity, event_id),
        )

        self.conn.commit()
        return self.get_reservation(reservation_id)

    def get_reservation(self, reservation_id: int) -> Reservation:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, code, user_id, event_id, ticket_type, quantity,
                   total_price, boys, girls, status, created_at,
                   payment_file_id, payment_file_type, admin_note,
                   reviewed_at, reviewed_by_tg_id, hold_applied
            FROM reservations
            WHERE id = ?
            """,
            (reservation_id,),
        )
        row = cursor.fetchone()
        return Reservation(**dict(row))

    def get_reservation_by_code(self, reservation_code: str) -> Optional[Reservation]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, code, user_id, event_id, ticket_type, quantity,
                   total_price, boys, girls, status, created_at,
                   payment_file_id, payment_file_type, admin_note,
                   reviewed_at, reviewed_by_tg_id, hold_applied
            FROM reservations
            WHERE code = ?
            """,
            (reservation_code,),
        )
        row = cursor.fetchone()
        return Reservation(**dict(row)) if row else None

    def list_reservations_for_user(self, user_id: int) -> List[Reservation]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, code, user_id, event_id, ticket_type, quantity,
                   total_price, boys, girls, status, created_at,
                   payment_file_id, payment_file_type, admin_note,
                   reviewed_at, reviewed_by_tg_id, hold_applied
            FROM reservations
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [Reservation(**dict(row)) for row in cursor.fetchall()]

    def list_attendees(self, reservation_id: int) -> List[sqlite3.Row]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, reservation_id, full_name, status FROM attendees WHERE reservation_id = ?",
            (reservation_id,),
        )
        return cursor.fetchall()

    def cancel_reservation_for_user(self, user_id: int, reservation_code: str) -> Tuple[bool, str, Optional[Reservation]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM reservations
            WHERE code = ? AND user_id = ?
            """,
            (reservation_code, user_id),
        )
        row = cursor.fetchone()
        if not row:
            return False, "Reservation not found for your account.", None

        if row["status"] in {STATUS_CANCELLED, STATUS_REJECTED}:
            return False, "Reservation is already inactive.", self.get_reservation(row["id"])

        self._release_hold(row, cursor)
        cursor.execute(
            """
            UPDATE reservations
            SET status = ?, hold_applied = 0
            WHERE id = ?
            """,
            (STATUS_CANCELLED, row["id"]),
        )
        self.conn.commit()
        return True, "Reservation cancelled. Please text admin for payment resolution.", self.get_reservation(row["id"])

    def approve_reservation(self, reservation_id: int, admin_tg_id: int) -> Tuple[bool, str, Optional[Reservation]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Reservation not found.", None
        if row["status"] != STATUS_PENDING:
            return False, f"Reservation is already {row['status']}.", self.get_reservation(reservation_id)

        cursor.execute(
            """
            UPDATE reservations
            SET status = ?, reviewed_at = ?, reviewed_by_tg_id = ?
            WHERE id = ?
            """,
            (STATUS_APPROVED, self._utc_now(), admin_tg_id, reservation_id),
        )
        self.conn.commit()
        return True, "Reservation approved.", self.get_reservation(reservation_id)

    def reject_reservation(
        self,
        reservation_id: int,
        admin_tg_id: int,
        admin_note: str,
    ) -> Tuple[bool, str, Optional[Reservation]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Reservation not found.", None
        if row["status"] != STATUS_PENDING:
            return False, f"Reservation is already {row['status']}.", self.get_reservation(reservation_id)

        self._release_hold(row, cursor)
        cursor.execute(
            """
            UPDATE reservations
            SET status = ?, admin_note = ?, reviewed_at = ?, reviewed_by_tg_id = ?, hold_applied = 0
            WHERE id = ?
            """,
            (STATUS_REJECTED, admin_note, self._utc_now(), admin_tg_id, reservation_id),
        )
        self.conn.commit()
        return True, "Reservation rejected.", self.get_reservation(reservation_id)

    def set_event_price(self, event_id: int, price_field: str, value: float) -> bool:
        field_map = {
            "early_boy": "early_bird_price",
            "early_girl": "early_bird_price_girl",
            "tier1_boy": "regular_tier1_price",
            "tier1_girl": "regular_tier1_price_girl",
            "tier2_boy": "regular_tier2_price",
            "tier2_girl": "regular_tier2_price_girl",
        }
        if price_field not in field_map:
            return False
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE events SET {field_map[price_field]} = ? WHERE id = ?",
            (value, event_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def list_blocked_users(self) -> List[sqlite3.Row]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE blocked = 1")
        return cursor.fetchall()

    def list_event_stats(
        self,
        sort_by: str = "date",
        search: Optional[str] = None,
        limit: int = 30,
    ) -> List[sqlite3.Row]:
        order_map = {
            "date": "e.event_datetime DESC",
            "title": "e.title COLLATE NOCASE ASC",
            "approved": "approved_tickets DESC, e.event_datetime DESC",
            "pending": "pending_tickets DESC, e.event_datetime DESC",
            "sold": "held_tickets DESC, e.event_datetime DESC",
            "revenue": "approved_revenue DESC, e.event_datetime DESC",
        }
        order_clause = order_map.get(sort_by, order_map["date"])

        query = """
            SELECT
                e.id,
                e.title,
                e.event_datetime,
                e.location,
                COALESCE(SUM(CASE WHEN r.status = ? THEN r.quantity ELSE 0 END), 0) AS approved_tickets,
                COALESCE(SUM(CASE WHEN r.status = ? THEN r.quantity ELSE 0 END), 0) AS pending_tickets,
                COALESCE(SUM(CASE WHEN r.status = ? THEN r.quantity ELSE 0 END), 0) AS rejected_tickets,
                COALESCE(SUM(CASE WHEN r.status = ? THEN r.quantity ELSE 0 END), 0) AS cancelled_tickets,
                COALESCE(
                    SUM(CASE WHEN r.status IN (?, ?) THEN r.quantity ELSE 0 END),
                    0
                ) AS held_tickets,
                COALESCE(SUM(CASE WHEN r.status = ? THEN r.total_price ELSE 0 END), 0) AS approved_revenue,
                COALESCE(SUM(CASE WHEN r.status = ? THEN r.total_price ELSE 0 END), 0) AS pending_revenue
            FROM events e
            LEFT JOIN reservations r ON r.event_id = e.id
            WHERE e.status = 'open'
        """
        params: List[object] = [
            STATUS_APPROVED,
            STATUS_PENDING,
            STATUS_REJECTED,
            STATUS_CANCELLED,
            STATUS_APPROVED,
            STATUS_PENDING,
            STATUS_APPROVED,
            STATUS_PENDING,
        ]
        if search:
            query += " AND (LOWER(e.title) LIKE ? OR LOWER(e.location) LIKE ?)"
            pattern = f"%{search.lower()}%"
            params.extend([pattern, pattern])

        query += " GROUP BY e.id"
        query += f" ORDER BY {order_clause} LIMIT ?"
        params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(query, tuple(params))
        return cursor.fetchall()

    def search_reservations(
        self,
        query_text: str,
        sort_by: str = "newest",
        limit: int = 20,
    ) -> List[sqlite3.Row]:
        order_map = {
            "newest": "r.created_at DESC",
            "amount": "r.total_price DESC, r.created_at DESC",
            "status": "r.status ASC, r.created_at DESC",
            "event_date": "e.event_datetime DESC, r.created_at DESC",
        }
        order_clause = order_map.get(sort_by, order_map["newest"])

        pattern = f"%{query_text.lower()}%"
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT
                r.id,
                r.code,
                r.status,
                r.quantity,
                r.boys,
                r.girls,
                r.total_price,
                r.created_at,
                e.id AS event_id,
                e.title AS event_title,
                e.event_datetime,
                u.tg_id,
                u.name AS buyer_name,
                u.surname AS buyer_surname,
                u.phone
            FROM reservations r
            JOIN events e ON e.id = r.event_id
            JOIN users u ON u.id = r.user_id
            WHERE
                LOWER(r.code) LIKE ?
                OR LOWER(e.title) LIKE ?
                OR LOWER(u.name) LIKE ?
                OR LOWER(u.surname) LIKE ?
                OR LOWER(COALESCE(u.phone, '')) LIKE ?
                OR CAST(u.tg_id AS TEXT) LIKE ?
            ORDER BY {order_clause}
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, pattern, pattern, limit),
        )
        return cursor.fetchall()

    def export_event_csv(self, event_id: int) -> List[List[str]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT r.code, r.ticket_type, r.boys, r.girls, r.quantity, r.total_price,
                   r.status, r.payment_file_type, r.payment_file_id, r.admin_note,
                   u.name, u.surname, u.phone
            FROM reservations r
            JOIN users u ON r.user_id = u.id
            WHERE r.event_id = ?
            ORDER BY r.created_at
            """,
            (event_id,),
        )
        rows = []
        for row in cursor.fetchall():
            rows.append(
                [
                    row["code"],
                    row["ticket_type"],
                    str(row["boys"]),
                    str(row["girls"]),
                    str(row["quantity"]),
                    str(row["total_price"]),
                    row["status"],
                    row["payment_file_type"],
                    row["payment_file_id"],
                    row["admin_note"],
                    row["name"],
                    row["surname"],
                    row["phone"],
                ]
            )
        return rows
