import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from ticketbot.models import Event, Reservation, User

EVENT_DT_FORMAT = "%Y-%m-%d %H:%M"
BUDAPEST_TZ = ZoneInfo("Europe/Budapest")

STATUS_PENDING = "pending_payment_review"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"
LEGACY_PENDING_STATUSES = {"pending"}


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
                ticket_tier TEXT NOT NULL DEFAULT '',
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
        if "gender" not in attendee_cols:
            cursor.execute("ALTER TABLE attendees ADD COLUMN gender TEXT NOT NULL DEFAULT 'unknown'")
        if "ticket_tier" not in attendee_cols:
            cursor.execute("ALTER TABLE attendees ADD COLUMN ticket_tier TEXT NOT NULL DEFAULT ''")
        cursor.execute(
            """
            UPDATE attendees
            SET full_name = TRIM(name || ' ' || COALESCE(surname, ''))
            WHERE full_name = ''
            """
        )
        self._backfill_attendee_genders(cursor)
        cursor.execute(
            """
            UPDATE attendees
            SET ticket_tier = (
                SELECT COALESCE(r.ticket_type, '')
                FROM reservations r
                WHERE r.id = attendees.reservation_id
            )
            WHERE ticket_tier = ''
            """
        )

        self.conn.commit()

    def _backfill_attendee_genders(self, cursor: sqlite3.Cursor) -> None:
        reservation_rows = cursor.execute(
            "SELECT id, boys, girls FROM reservations ORDER BY id"
        ).fetchall()
        for reservation in reservation_rows:
            attendee_rows = cursor.execute(
                """
                SELECT id
                FROM attendees
                WHERE reservation_id = ?
                ORDER BY id
                """,
                (reservation["id"],),
            ).fetchall()
            boys = int(reservation["boys"] or 0)
            girls = int(reservation["girls"] or 0)
            for idx, attendee in enumerate(attendee_rows):
                if idx < boys:
                    gender = "boy"
                elif idx < boys + girls:
                    gender = "girl"
                else:
                    gender = "unknown"
                cursor.execute(
                    "UPDATE attendees SET gender = ? WHERE id = ? AND (gender IS NULL OR gender = '' OR gender = 'unknown')",
                    (gender, attendee["id"]),
                )

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

    def _tier_sequence(self, event: Event) -> List[Dict[str, Any]]:
        return [
            {
                "key": "early",
                "name": "Early Bird",
                "remaining": int(event.early_bird_qty),
                "boy_price": float(event.early_bird_price),
                "girl_price": float(event.early_bird_price_girl),
                "qty_column": "early_bird_qty",
            },
            {
                "key": "tier1",
                "name": "Regular Tier-1",
                "remaining": int(event.regular_tier1_qty),
                "boy_price": float(event.regular_tier1_price),
                "girl_price": float(event.regular_tier1_price_girl),
                "qty_column": "regular_tier1_qty",
            },
            {
                "key": "tier2",
                "name": "Regular Tier-2",
                "remaining": int(event.regular_tier2_qty),
                "boy_price": float(event.regular_tier2_price),
                "girl_price": float(event.regular_tier2_price_girl),
                "qty_column": "regular_tier2_qty",
            },
        ]

    def _allocate_tier_plan(self, event: Event, boys: int, girls: int) -> Dict[str, Any]:
        quantity = int(boys) + int(girls)
        if quantity <= 0:
            raise ValueError("At least one attendee is required")

        total_remaining = self.total_remaining(event)
        if quantity > total_remaining:
            raise ValueError("Not enough tickets remaining across all tiers")

        genders = (["boy"] * int(boys)) + (["girl"] * int(girls))
        tiers = self._tier_sequence(event)
        tier_remaining = {tier["key"]: int(tier["remaining"]) for tier in tiers}
        tier_lookup = {tier["key"]: tier for tier in tiers}

        attendee_allocations: List[Dict[str, Any]] = []
        tier_usage: Dict[str, Dict[str, Any]] = {}
        total_price = 0.0

        for gender in genders:
            selected_tier = None
            for tier in tiers:
                key = tier["key"]
                if tier_remaining[key] > 0:
                    selected_tier = key
                    tier_remaining[key] -= 1
                    break
            if not selected_tier:
                raise ValueError("Event is sold out")

            tier_info = tier_lookup[selected_tier]
            unit_price = float(tier_info["boy_price"] if gender == "boy" else tier_info["girl_price"])
            total_price += unit_price
            attendee_allocations.append(
                {
                    "tier_key": selected_tier,
                    "gender": gender,
                    "unit_price": unit_price,
                }
            )
            if selected_tier not in tier_usage:
                tier_usage[selected_tier] = {
                    "tier_key": selected_tier,
                    "tier_name": tier_info["name"],
                    "count": 0,
                    "boys": 0,
                    "girls": 0,
                    "boy_price": float(tier_info["boy_price"]),
                    "girl_price": float(tier_info["girl_price"]),
                    "subtotal": 0.0,
                }
            usage = tier_usage[selected_tier]
            usage["count"] += 1
            usage["boys"] += 1 if gender == "boy" else 0
            usage["girls"] += 1 if gender == "girl" else 0
            usage["subtotal"] += unit_price

        breakdown = [tier_usage[tier["key"]] for tier in tiers if tier["key"] in tier_usage]
        hold_counts = {key: value["count"] for key, value in tier_usage.items()}
        primary_tier_key = attendee_allocations[0]["tier_key"] if attendee_allocations else "early"
        return {
            "quantity": quantity,
            "total_price": total_price,
            "primary_tier_key": primary_tier_key,
            "attendee_allocations": attendee_allocations,
            "hold_counts": hold_counts,
            "breakdown": breakdown,
        }

    def quote_booking(self, event_id: int, boys: int, girls: int) -> Dict[str, Any]:
        event = self.get_event(event_id)
        if not event:
            raise ValueError("Event not found")
        plan = self._allocate_tier_plan(event, boys, girls)
        return {
            "event_id": event.id,
            "event_title": event.title,
            "boys": int(boys),
            "girls": int(girls),
            "quantity": plan["quantity"],
            "total_price": float(plan["total_price"]),
            "breakdown": plan["breakdown"],
        }

    def _normalize_gender(self, value: str) -> Optional[str]:
        mapping = {
            "boy": "boy",
            "male": "boy",
            "m": "boy",
            "girl": "girl",
            "female": "girl",
            "f": "girl",
        }
        return mapping.get((value or "").strip().lower())

    def _name_parts(self, name: str, surname: str, full_name: str) -> Tuple[str, str]:
        left = (name or "").strip()
        right = (surname or "").strip()
        if left and right:
            return left, right

        merged = (full_name or "").strip() or left
        if not merged:
            return "", ""
        tokens = merged.split()
        if len(tokens) == 1:
            return tokens[0], ""
        return tokens[0], " ".join(tokens[1:])

    def _ensure_user_for_tg(self, tg_id: int, cursor: sqlite3.Cursor) -> int:
        cursor.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
        existing = cursor.fetchone()
        if existing:
            return int(existing["id"])
        cursor.execute(
            """
            INSERT INTO users (tg_id, name, surname, phone, blocked, blocked_reason)
            VALUES (?, ?, ?, ?, 0, '')
            """,
            (tg_id, "Admin", "User", "admin"),
        )
        return int(cursor.lastrowid)

    def _release_hold(self, reservation_row: sqlite3.Row, cursor: sqlite3.Cursor) -> None:
        if reservation_row["hold_applied"] != 1:
            return
        hold_counts = self._reservation_hold_counts(reservation_id=int(reservation_row["id"]), cursor=cursor)
        if not hold_counts:
            ticket_type = (reservation_row["ticket_type"] or "").strip()
            if ticket_type:
                hold_counts = {ticket_type: int(reservation_row["quantity"] or 0)}
        for tier_key, qty in hold_counts.items():
            if qty <= 0:
                continue
            qty_column = self._tier_qty_column(tier_key)
            cursor.execute(
                f"UPDATE events SET {qty_column} = {qty_column} + ? WHERE id = ?",
                (int(qty), reservation_row["event_id"]),
            )

    def _reservation_hold_counts(self, reservation_id: int, cursor: sqlite3.Cursor) -> Dict[str, int]:
        cursor.execute(
            """
            SELECT COALESCE(ticket_tier, '') AS tier_key, COUNT(*) AS cnt
            FROM attendees
            WHERE reservation_id = ?
            GROUP BY COALESCE(ticket_tier, '')
            """,
            (reservation_id,),
        )
        counts: Dict[str, int] = {}
        for row in cursor.fetchall():
            key = (row["tier_key"] or "").strip()
            if key in {"early", "tier1", "tier2"}:
                counts[key] = int(row["cnt"])
        return counts

    def _is_admin_mutable_reservation_status(self, status: str) -> bool:
        normalized = (status or "").strip().lower()
        return normalized in {
            STATUS_PENDING,
            STATUS_APPROVED,
            *LEGACY_PENDING_STATUSES,
            "pending_payment",
            "pending_review",
            "pending_payment_approval",
        }

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
        for tier in self._tier_sequence(event):
            if tier["remaining"] > 0:
                return {
                    "key": tier["key"],
                    "name": tier["name"],
                    "boy_price": tier["boy_price"],
                    "girl_price": tier["girl_price"],
                    "remaining": tier["remaining"],
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

        plan = self._allocate_tier_plan(event, boys, girls)
        quantity = int(plan["quantity"])
        if len(attendees) != quantity:
            raise ValueError("Attendee count does not match boys + girls")
        total_price = float(plan["total_price"])
        code = f"R{event_id}-{uuid.uuid4().hex[:8].upper()}"

        cursor = self.conn.cursor()
        reservation_cols = self._table_columns("reservations")
        avg_price = (total_price / quantity) if quantity > 0 else 0.0
        insert_values = {
            "code": code,
            "user_id": user_id,
            "event_id": event_id,
            "ticket_type": plan["primary_tier_key"],
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

        for attendee_index, full_name in enumerate(attendees):
            attendee_plan = plan["attendee_allocations"][attendee_index]
            attendee_gender = attendee_plan["gender"]
            attendee_tier = attendee_plan["tier_key"]
            first_name, surname = self._name_parts("", "", full_name)
            cursor.execute(
                """
                INSERT INTO attendees (reservation_id, name, surname, full_name, gender, ticket_tier)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (reservation_id, first_name, surname, full_name, attendee_gender, attendee_tier),
            )

        hold_counts = plan["hold_counts"]
        for tier_key, tier_qty in hold_counts.items():
            qty_column = self._tier_qty_column(tier_key)
            cursor.execute(
                f"UPDATE events SET {qty_column} = {qty_column} - ? WHERE id = ? AND {qty_column} >= ?",
                (int(tier_qty), event_id, int(tier_qty)),
            )
            if cursor.rowcount <= 0:
                self.conn.rollback()
                raise ValueError("Not enough tickets remaining across all tiers")

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
            "SELECT id, reservation_id, name, surname, full_name, gender, ticket_tier, status FROM attendees WHERE reservation_id = ? ORDER BY id",
            (reservation_id,),
        )
        return cursor.fetchall()

    def _reservation_row_by_code(self, reservation_code: str, cursor: sqlite3.Cursor) -> Optional[sqlite3.Row]:
        cursor.execute("SELECT * FROM reservations WHERE code = ?", (reservation_code,))
        return cursor.fetchone()

    def _reservation_row_by_id(self, reservation_id: int, cursor: sqlite3.Cursor) -> Optional[sqlite3.Row]:
        cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
        return cursor.fetchone()

    def _reservation_unit_price(
        self,
        reservation_row: sqlite3.Row,
        event: Event,
        gender: str,
        attendee_tier: Optional[str] = None,
    ) -> float:
        tier_key = (attendee_tier or reservation_row["ticket_type"] or "").strip()
        if tier_key in {"early", "tier1", "tier2"}:
            boy_price, girl_price = self._tier_prices(event, tier_key)
        else:
            boy_price, girl_price = (0.0, 0.0)
        if gender == "boy":
            return float(boy_price)
        if gender == "girl":
            return float(girl_price)
        quantity = int(reservation_row["quantity"] or 0)
        total_price = float(reservation_row["total_price"] or 0)
        return (total_price / quantity) if quantity > 0 else 0.0

    def _update_legacy_reservation_fields(
        self,
        cursor: sqlite3.Cursor,
        reservation_id: int,
        reservation_cols: set,
        quantity: int,
        total_price: float,
    ) -> None:
        updates: Dict[str, Any] = {}
        if "price_per_ticket" in reservation_cols:
            updates["price_per_ticket"] = (total_price / quantity) if quantity > 0 else 0.0
        if "paid_tickets" in reservation_cols:
            updates["paid_tickets"] = quantity
        if not updates:
            return
        assignments = ", ".join([f"{col} = ?" for col in updates.keys()])
        params = list(updates.values()) + [reservation_id]
        cursor.execute(f"UPDATE reservations SET {assignments} WHERE id = ?", tuple(params))

    def admin_add_guest(
        self,
        reservation_code: str,
        full_name: str,
        gender_raw: str,
    ) -> Tuple[bool, str, Optional[Reservation]]:
        gender = self._normalize_gender(gender_raw)
        if gender is None:
            return False, "Gender must be boy or girl.", None

        cursor = self.conn.cursor()
        reservation_row = self._reservation_row_by_code(reservation_code, cursor)
        if not reservation_row:
            return False, "Reservation code not found.", None
        if not self._is_admin_mutable_reservation_status(reservation_row["status"]):
            return False, "Guest can be added only to pending/approved reservations.", None

        event = self.get_event(reservation_row["event_id"])
        if not event:
            return False, "Event not found for reservation.", None

        try:
            add_plan = self._allocate_tier_plan(event, 1 if gender == "boy" else 0, 1 if gender == "girl" else 0)
        except ValueError:
            return False, "No tickets left across all tiers for adding guest.", None
        attendee_tier = add_plan["attendee_allocations"][0]["tier_key"]
        add_price = float(add_plan["attendee_allocations"][0]["unit_price"])
        qty_column = self._tier_qty_column(attendee_tier)
        if reservation_row["hold_applied"] == 1:
            cursor.execute(
                f"UPDATE events SET {qty_column} = {qty_column} - 1 WHERE id = ? AND {qty_column} > 0",
                (reservation_row["event_id"],),
            )
            if cursor.rowcount == 0:
                self.conn.rollback()
                return False, "No tickets left across all tiers for adding guest.", None
        new_quantity = int(reservation_row["quantity"]) + 1
        new_boys = int(reservation_row["boys"]) + (1 if gender == "boy" else 0)
        new_girls = int(reservation_row["girls"]) + (1 if gender == "girl" else 0)
        new_total = float(reservation_row["total_price"]) + float(add_price)

        cursor.execute(
            """
            UPDATE reservations
            SET quantity = ?, boys = ?, girls = ?, total_price = ?
            WHERE id = ?
            """,
            (new_quantity, new_boys, new_girls, new_total, reservation_row["id"]),
        )
        reservation_cols = self._table_columns("reservations")
        self._update_legacy_reservation_fields(
            cursor=cursor,
            reservation_id=reservation_row["id"],
            reservation_cols=reservation_cols,
            quantity=new_quantity,
            total_price=new_total,
        )
        cursor.execute(
            """
            INSERT INTO attendees (reservation_id, name, surname, full_name, gender, ticket_tier)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (reservation_row["id"], *self._name_parts("", "", full_name), full_name, gender, attendee_tier),
        )
        self.conn.commit()
        updated = self.get_reservation(reservation_row["id"])
        return True, "Guest added successfully.", updated

    def admin_add_guest_by_event(
        self,
        admin_tg_id: int,
        event_id: int,
        name: str,
        surname: str,
        gender_raw: str,
        allow_missing_surname: bool = False,
    ) -> Tuple[bool, str, Optional[Reservation]]:
        gender = self._normalize_gender(gender_raw)
        if gender is None:
            return False, "Gender must be boy or girl.", None

        clean_name = (name or "").strip()
        clean_surname = (surname or "").strip()
        if not clean_name or (not clean_surname and not allow_missing_surname):
            return False, "Both name and surname are required.", None

        event = self.get_event(event_id)
        if not event:
            return False, "Event not found.", None

        active_tier = self.active_tier(event)
        if not active_tier:
            return False, "Event is sold out.", None

        price = float(active_tier["boy_price"] if gender == "boy" else active_tier["girl_price"])
        code = f"A{event_id}-{uuid.uuid4().hex[:8].upper()}"
        quantity = 1
        boys = 1 if gender == "boy" else 0
        girls = 1 if gender == "girl" else 0
        full_name = f"{clean_name} {clean_surname}".strip()

        cursor = self.conn.cursor()
        user_id = self._ensure_user_for_tg(admin_tg_id, cursor)

        qty_column = self._tier_qty_column(active_tier["key"])
        cursor.execute(
            f"UPDATE events SET {qty_column} = {qty_column} - 1 WHERE id = ? AND {qty_column} > 0",
            (event_id,),
        )
        if cursor.rowcount <= 0:
            self.conn.rollback()
            return False, "No tickets left in current tier.", None

        reservation_cols = self._table_columns("reservations")
        insert_values: Dict[str, Any] = {
            "code": code,
            "user_id": user_id,
            "event_id": event_id,
            "ticket_type": active_tier["key"],
            "quantity": quantity,
            "total_price": price,
            "boys": boys,
            "girls": girls,
            "status": STATUS_APPROVED,
            "created_at": self._utc_now(),
        }
        if "price_per_ticket" in reservation_cols:
            insert_values["price_per_ticket"] = price
        if "paid_tickets" in reservation_cols:
            insert_values["paid_tickets"] = quantity
        if "credit_used_tickets" in reservation_cols:
            insert_values["credit_used_tickets"] = 0
        if "credit_source_codes" in reservation_cols:
            insert_values["credit_source_codes"] = ""
        if "payment_file_id" in reservation_cols:
            insert_values["payment_file_id"] = ""
        if "payment_file_type" in reservation_cols:
            insert_values["payment_file_type"] = ""
        if "admin_note" in reservation_cols:
            insert_values["admin_note"] = "Added by admin dashboard"
        if "reviewed_at" in reservation_cols:
            insert_values["reviewed_at"] = self._utc_now()
        if "reviewed_by_tg_id" in reservation_cols:
            insert_values["reviewed_by_tg_id"] = admin_tg_id
        if "hold_applied" in reservation_cols:
            insert_values["hold_applied"] = 1

        columns = list(insert_values.keys())
        placeholders = ", ".join(["?"] * len(columns))
        cursor.execute(
            f"INSERT INTO reservations ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(insert_values[col] for col in columns),
        )
        reservation_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO attendees (reservation_id, name, surname, full_name, gender, ticket_tier)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (reservation_id, clean_name, clean_surname, full_name, gender, active_tier["key"]),
        )
        self.conn.commit()
        return True, "Guest added successfully.", self.get_reservation(reservation_id)

    def admin_import_guest_by_event(
        self,
        admin_tg_id: int,
        event_id: int,
        name: str,
        surname: str,
    ) -> Tuple[bool, str, Optional[Reservation]]:
        clean_name = (name or "").strip()
        clean_surname = (surname or "").strip()
        if not clean_name:
            return False, "Name is required.", None

        event = self.get_event(event_id)
        if not event:
            return False, "Event not found.", None

        full_name = f"{clean_name} {clean_surname}".strip()
        code = f"I{event_id}-{uuid.uuid4().hex[:8].upper()}"
        cursor = self.conn.cursor()
        user_id = self._ensure_user_for_tg(admin_tg_id, cursor)

        reservation_cols = self._table_columns("reservations")
        insert_values: Dict[str, Any] = {
            "code": code,
            "user_id": user_id,
            "event_id": event_id,
            "ticket_type": "",
            "quantity": 1,
            "total_price": 0.0,
            "boys": 0,
            "girls": 0,
            "status": STATUS_APPROVED,
            "created_at": self._utc_now(),
        }
        if "price_per_ticket" in reservation_cols:
            insert_values["price_per_ticket"] = 0.0
        if "paid_tickets" in reservation_cols:
            insert_values["paid_tickets"] = 1
        if "credit_used_tickets" in reservation_cols:
            insert_values["credit_used_tickets"] = 0
        if "credit_source_codes" in reservation_cols:
            insert_values["credit_source_codes"] = ""
        if "payment_file_id" in reservation_cols:
            insert_values["payment_file_id"] = ""
        if "payment_file_type" in reservation_cols:
            insert_values["payment_file_type"] = ""
        if "admin_note" in reservation_cols:
            insert_values["admin_note"] = "Imported from Excel"
        if "reviewed_at" in reservation_cols:
            insert_values["reviewed_at"] = self._utc_now()
        if "reviewed_by_tg_id" in reservation_cols:
            insert_values["reviewed_by_tg_id"] = admin_tg_id
        if "hold_applied" in reservation_cols:
            insert_values["hold_applied"] = 0

        columns = list(insert_values.keys())
        placeholders = ", ".join(["?"] * len(columns))
        cursor.execute(
            f"INSERT INTO reservations ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(insert_values[col] for col in columns),
        )
        reservation_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO attendees (reservation_id, name, surname, full_name, gender, ticket_tier)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (reservation_id, clean_name, clean_surname, full_name, "unknown", ""),
        )
        self.conn.commit()
        return True, "Guest imported successfully.", self.get_reservation(reservation_id)

    def admin_remove_guest(self, attendee_id: int) -> Tuple[bool, str, Optional[Reservation]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                a.id AS attendee_id,
                a.full_name,
                COALESCE(a.gender, 'unknown') AS gender,
                COALESCE(a.ticket_tier, '') AS attendee_tier,
                r.*
            FROM attendees a
            JOIN reservations r ON r.id = a.reservation_id
            WHERE a.id = ?
            """,
            (attendee_id,),
        )
        row = cursor.fetchone()
        if not row:
            return False, "Attendee not found.", None
        if not self._is_admin_mutable_reservation_status(row["status"]):
            return False, "Guest can be removed only from pending/approved reservations.", None

        event = self.get_event(row["event_id"])
        if not event:
            return False, "Event not found for reservation.", None

        gender = row["gender"] if row["gender"] in {"boy", "girl"} else "unknown"
        unit_price = self._reservation_unit_price(row, event, gender, attendee_tier=row["attendee_tier"])
        new_quantity = int(row["quantity"]) - 1

        if gender == "boy":
            new_boys = max(0, int(row["boys"]) - 1)
            new_girls = int(row["girls"])
        elif gender == "girl":
            new_boys = int(row["boys"])
            new_girls = max(0, int(row["girls"]) - 1)
        elif int(row["boys"]) > 0:
            new_boys = int(row["boys"]) - 1
            new_girls = int(row["girls"])
        else:
            new_boys = int(row["boys"])
            new_girls = max(0, int(row["girls"]) - 1)

        new_total = max(0.0, float(row["total_price"]) - float(unit_price))
        cursor.execute("DELETE FROM attendees WHERE id = ?", (attendee_id,))

        if row["hold_applied"] == 1:
            release_tier = row["attendee_tier"] if row["attendee_tier"] in {"early", "tier1", "tier2"} else row["ticket_type"]
            qty_column = self._tier_qty_column(release_tier)
            cursor.execute(
                f"UPDATE events SET {qty_column} = {qty_column} + 1 WHERE id = ?",
                (row["event_id"],),
            )

        if new_quantity <= 0:
            cursor.execute(
                """
                UPDATE reservations
                SET quantity = 0, boys = 0, girls = 0, total_price = 0,
                    status = ?, hold_applied = 0
                WHERE id = ?
                """,
                (STATUS_CANCELLED, row["id"]),
            )
            reservation_cols = self._table_columns("reservations")
            self._update_legacy_reservation_fields(
                cursor=cursor,
                reservation_id=row["id"],
                reservation_cols=reservation_cols,
                quantity=0,
                total_price=0.0,
            )
            self.conn.commit()
            updated = self.get_reservation(row["id"])
            return True, "Guest removed and reservation cancelled.", updated

        cursor.execute(
            """
            UPDATE reservations
            SET quantity = ?, boys = ?, girls = ?, total_price = ?
            WHERE id = ?
            """,
            (new_quantity, new_boys, new_girls, new_total, row["id"]),
        )
        reservation_cols = self._table_columns("reservations")
        self._update_legacy_reservation_fields(
            cursor=cursor,
            reservation_id=row["id"],
            reservation_cols=reservation_cols,
            quantity=new_quantity,
            total_price=new_total,
        )
        self.conn.commit()
        updated = self.get_reservation(row["id"])
        return True, "Guest removed successfully.", updated

    def admin_remove_guest_by_name(
        self,
        event_id: int,
        name: str,
        surname: str,
    ) -> Tuple[bool, str, Optional[Reservation]]:
        clean_name = (name or "").strip()
        clean_surname = (surname or "").strip()
        if not clean_name or not clean_surname:
            return False, "Both name and surname are required.", None

        full_name = f"{clean_name} {clean_surname}".strip()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                a.id AS attendee_id,
                a.full_name,
                COALESCE(a.gender, 'unknown') AS gender,
                COALESCE(a.ticket_tier, '') AS attendee_tier,
                r.*
            FROM attendees a
            JOIN reservations r ON r.id = a.reservation_id
            WHERE r.event_id = ?
              AND LOWER(TRIM(r.status)) IN (?, ?, ?, ?, ?, ?)
              AND (
                    LOWER(TRIM(a.full_name)) = LOWER(TRIM(?))
                    OR (LOWER(TRIM(a.name)) = LOWER(TRIM(?)) AND LOWER(TRIM(a.surname)) = LOWER(TRIM(?)))
              )
            ORDER BY a.id DESC
            LIMIT 1
            """,
            (
                event_id,
                STATUS_PENDING,
                STATUS_APPROVED,
                "pending",
                "pending_payment",
                "pending_review",
                "pending_payment_approval",
                full_name,
                clean_name,
                clean_surname,
            ),
        )
        row = cursor.fetchone()
        if not row:
            return False, "Guest not found for selected event.", None

        event = self.get_event(row["event_id"])
        if not event:
            return False, "Event not found for reservation.", None

        gender = row["gender"] if row["gender"] in {"boy", "girl"} else "unknown"
        unit_price = self._reservation_unit_price(row, event, gender, attendee_tier=row["attendee_tier"])
        new_quantity = int(row["quantity"]) - 1

        if gender == "boy":
            new_boys = max(0, int(row["boys"]) - 1)
            new_girls = int(row["girls"])
        elif gender == "girl":
            new_boys = int(row["boys"])
            new_girls = max(0, int(row["girls"]) - 1)
        elif int(row["boys"]) > 0:
            new_boys = int(row["boys"]) - 1
            new_girls = int(row["girls"])
        else:
            new_boys = int(row["boys"])
            new_girls = max(0, int(row["girls"]) - 1)

        cursor.execute("DELETE FROM attendees WHERE id = ?", (row["attendee_id"],))
        if row["hold_applied"] == 1:
            release_tier = row["attendee_tier"] if row["attendee_tier"] in {"early", "tier1", "tier2"} else row["ticket_type"]
            qty_column = self._tier_qty_column(release_tier)
            cursor.execute(
                f"UPDATE events SET {qty_column} = {qty_column} + 1 WHERE id = ?",
                (row["event_id"],),
            )

        if new_quantity <= 0:
            cursor.execute(
                """
                UPDATE reservations
                SET quantity = 0, boys = 0, girls = 0, total_price = 0,
                    status = ?, hold_applied = 0
                WHERE id = ?
                """,
                (STATUS_CANCELLED, row["id"]),
            )
            reservation_cols = self._table_columns("reservations")
            self._update_legacy_reservation_fields(
                cursor=cursor,
                reservation_id=row["id"],
                reservation_cols=reservation_cols,
                quantity=0,
                total_price=0.0,
            )
        else:
            new_total = max(0.0, float(row["total_price"]) - float(unit_price))
            cursor.execute(
                """
                UPDATE reservations
                SET quantity = ?, boys = ?, girls = ?, total_price = ?
                WHERE id = ?
                """,
                (new_quantity, new_boys, new_girls, new_total, row["id"]),
            )
            reservation_cols = self._table_columns("reservations")
            self._update_legacy_reservation_fields(
                cursor=cursor,
                reservation_id=row["id"],
                reservation_cols=reservation_cols,
                quantity=new_quantity,
                total_price=new_total,
            )

        self.conn.commit()
        return True, "Guest removed successfully.", self.get_reservation(row["id"])

    def admin_rename_guest(self, attendee_id: int, full_name: str) -> Tuple[bool, str]:
        clean = (full_name or "").strip()
        if not clean:
            return False, "Full name is required."
        parts = [part for part in clean.split() if part]
        first_name = parts[0]
        surname = " ".join(parts[1:]) if len(parts) > 1 else ""
        normalized = f"{first_name} {surname}".strip()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE attendees
            SET full_name = ?, name = ?, surname = ?
            WHERE id = ?
            """,
            (normalized, first_name, surname, attendee_id),
        )
        self.conn.commit()
        if cursor.rowcount <= 0:
            return False, "Attendee not found."
        return True, "Guest name updated."

    def list_guests(
        self,
        sort_by: str = "newest",
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[sqlite3.Row]:
        order_map = {
            "newest": "a.id DESC",
            "name": "a.full_name COLLATE NOCASE ASC, a.id DESC",
            "event": "e.event_datetime DESC, a.id DESC",
            "reservation": "r.code ASC, a.id DESC",
            "status": "r.status ASC, a.id DESC",
        }
        order_clause = order_map.get(sort_by, order_map["newest"])
        query = """
            SELECT
                a.id AS attendee_id,
                a.full_name,
                COALESCE(a.gender, 'unknown') AS gender,
                r.id AS reservation_id,
                r.code AS reservation_code,
                r.status AS reservation_status,
                e.id AS event_id,
                e.title AS event_title,
                e.event_datetime,
                u.tg_id AS buyer_tg_id,
                u.name AS buyer_name,
                u.surname AS buyer_surname
            FROM attendees a
            JOIN reservations r ON r.id = a.reservation_id
            JOIN events e ON e.id = r.event_id
            JOIN users u ON u.id = r.user_id
            WHERE 1 = 1
        """
        params: List[Any] = []
        if search:
            pattern = f"%{search.lower()}%"
            query += """
                AND (
                    LOWER(a.full_name) LIKE ?
                    OR LOWER(r.code) LIKE ?
                    OR LOWER(e.title) LIKE ?
                    OR LOWER(u.name) LIKE ?
                    OR LOWER(u.surname) LIKE ?
                    OR CAST(u.tg_id AS TEXT) LIKE ?
                )
            """
            params.extend([pattern, pattern, pattern, pattern, pattern, pattern])
        query += f" ORDER BY {order_clause}"
        if limit is not None and int(limit) > 0:
            query += " LIMIT ?"
            params.append(int(limit))
        cursor = self.conn.cursor()
        cursor.execute(query, tuple(params))
        return cursor.fetchall()

    def get_guest(self, attendee_id: int) -> Optional[sqlite3.Row]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                a.id AS attendee_id,
                a.full_name,
                COALESCE(a.gender, 'unknown') AS gender,
                r.id AS reservation_id,
                r.code AS reservation_code,
                r.status AS reservation_status,
                e.id AS event_id,
                e.title AS event_title,
                e.event_datetime,
                u.tg_id AS buyer_tg_id,
                u.name AS buyer_name,
                u.surname AS buyer_surname
            FROM attendees a
            JOIN reservations r ON r.id = a.reservation_id
            JOIN events e ON e.id = r.event_id
            JOIN users u ON u.id = r.user_id
            WHERE a.id = ?
            """,
            (attendee_id,),
        )
        return cursor.fetchone()

    def list_guest_name_pairs(self) -> List[Tuple[str, str]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT name, surname, full_name
            FROM attendees
            ORDER BY id
            """
        )
        rows = []
        for row in cursor.fetchall():
            first, last = self._name_parts(
                name=row["name"],
                surname=row["surname"],
                full_name=row["full_name"],
            )
            rows.append((first, last))
        return rows

    def list_active_reservations(self, search: Optional[str] = None, limit: int = 12) -> List[sqlite3.Row]:
        query = """
            SELECT
                r.id AS reservation_id,
                r.code AS reservation_code,
                r.status AS reservation_status,
                r.quantity,
                r.boys,
                r.girls,
                r.total_price,
                r.created_at,
                e.id AS event_id,
                e.title AS event_title,
                e.event_datetime,
                u.tg_id AS buyer_tg_id,
                u.name AS buyer_name,
                u.surname AS buyer_surname
            FROM reservations r
            JOIN events e ON e.id = r.event_id
            JOIN users u ON u.id = r.user_id
            WHERE r.status IN (?, ?)
        """
        params: List[Any] = [STATUS_PENDING, STATUS_APPROVED]
        if search:
            pattern = f"%{search.lower()}%"
            query += """
                AND (
                    LOWER(r.code) LIKE ?
                    OR LOWER(e.title) LIKE ?
                    OR LOWER(u.name) LIKE ?
                    OR LOWER(u.surname) LIKE ?
                    OR CAST(u.tg_id AS TEXT) LIKE ?
                )
            """
            params.extend([pattern, pattern, pattern, pattern, pattern])
        query += " ORDER BY r.created_at DESC LIMIT ?"
        params.append(limit)
        cursor = self.conn.cursor()
        cursor.execute(query, tuple(params))
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

    def set_event_fields(self, event_id: int, updates: Dict[str, Any]) -> Tuple[bool, str]:
        field_map = {
            "title": "title",
            "location": "location",
            "datetime": "event_datetime",
            "caption": "caption",
            "photo": "photo_file_id",
            "early_boy": "early_bird_price",
            "early_girl": "early_bird_price_girl",
            "early_qty": "early_bird_qty",
            "tier1_boy": "regular_tier1_price",
            "tier1_girl": "regular_tier1_price_girl",
            "tier1_qty": "regular_tier1_qty",
            "tier2_boy": "regular_tier2_price",
            "tier2_girl": "regular_tier2_price_girl",
            "tier2_qty": "regular_tier2_qty",
        }
        if not updates:
            return False, "No fields provided."

        assignments: List[str] = []
        params: List[Any] = []
        for key, value in updates.items():
            if key not in field_map:
                return False, f"Unsupported field: {key}"
            column = field_map[key]
            if key == "datetime":
                try:
                    self.parse_event_datetime(str(value))
                except ValueError:
                    return False, "Invalid datetime format. Use YYYY-MM-DD HH:MM"
            if key.endswith("_qty"):
                try:
                    ivalue = int(value)
                except (TypeError, ValueError):
                    return False, f"{key} must be integer."
                if ivalue < 0:
                    return False, f"{key} must be non-negative."
                value = ivalue
            if key in {"early_boy", "early_girl", "tier1_boy", "tier1_girl", "tier2_boy", "tier2_girl"}:
                try:
                    fvalue = float(value)
                except (TypeError, ValueError):
                    return False, f"{key} must be number."
                if fvalue < 0:
                    return False, f"{key} must be non-negative."
                value = fvalue

            assignments.append(f"{column} = ?")
            params.append(value)

        params.append(event_id)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE events SET {', '.join(assignments)} WHERE id = ?", tuple(params))
        self.conn.commit()
        if cursor.rowcount <= 0:
            return False, "Event not found."
        return True, "Event updated."

    def delete_event(self, event_id: int) -> Tuple[bool, str, Dict[str, int]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, title FROM events WHERE id = ?", (event_id,))
        event_row = cursor.fetchone()
        if not event_row:
            return False, "Event not found.", {"events": 0, "reservations": 0, "attendees": 0}

        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM reservations WHERE event_id = ?",
            (event_id,),
        )
        reservation_count = int(cursor.fetchone()["cnt"])
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM attendees
            WHERE reservation_id IN (SELECT id FROM reservations WHERE event_id = ?)
            """,
            (event_id,),
        )
        attendee_count = int(cursor.fetchone()["cnt"])

        try:
            cursor.execute(
                """
                DELETE FROM attendees
                WHERE reservation_id IN (SELECT id FROM reservations WHERE event_id = ?)
                """,
                (event_id,),
            )
            cursor.execute("DELETE FROM reservations WHERE event_id = ?", (event_id,))
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            self.conn.commit()
        except sqlite3.Error as exc:
            self.conn.rollback()
            return False, f"Failed to delete event: {exc}", {"events": 0, "reservations": 0, "attendees": 0}

        return (
            True,
            f"Event deleted. Removed {reservation_count} reservations and {attendee_count} guests.",
            {"events": 1, "reservations": reservation_count, "attendees": attendee_count},
        )

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
