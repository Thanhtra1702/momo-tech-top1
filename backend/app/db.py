"""SQLite: mỗi lần dùng mở một kết nối riêng (an toàn với thread pool của FastAPI)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, title_norm TEXT NOT NULL,
  venue TEXT NOT NULL, city TEXT NOT NULL, city_norm TEXT NOT NULL, starts_at TEXT NOT NULL,
  price_vnd INTEGER NOT NULL, seats_left INTEGER NOT NULL, rating REAL NOT NULL,
  tags TEXT NOT NULL DEFAULT '[]', tags_norm TEXT NOT NULL DEFAULT '', deeplink TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_city ON events(city_norm, starts_at);

CREATE TABLE IF NOT EXISTS transport (
  id TEXT PRIMARY KEY, mode TEXT NOT NULL, carrier TEXT NOT NULL,
  origin TEXT NOT NULL, origin_norm TEXT NOT NULL, destination TEXT NOT NULL, destination_norm TEXT NOT NULL,
  departs_at TEXT NOT NULL, arrives_at TEXT NOT NULL, price_vnd INTEGER NOT NULL,
  seats_left INTEGER NOT NULL, baggage_kg INTEGER NOT NULL DEFAULT 0, refundable INTEGER NOT NULL DEFAULT 0,
  deeplink TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transport_route ON transport(origin_norm, destination_norm, departs_at);

CREATE TABLE IF NOT EXISTS lodging (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, name_norm TEXT NOT NULL, kind TEXT NOT NULL,
  city TEXT NOT NULL, city_norm TEXT NOT NULL, price_per_night_vnd INTEGER NOT NULL,
  rooms_left INTEGER NOT NULL, rating REAL NOT NULL, amenities TEXT NOT NULL DEFAULT '[]',
  amenities_norm TEXT NOT NULL DEFAULT '', free_cancellation INTEGER NOT NULL DEFAULT 0, deeplink TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lodging_city ON lodging(city_norm);

CREATE TABLE IF NOT EXISTS tours (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, name_norm TEXT NOT NULL, city TEXT NOT NULL, city_norm TEXT NOT NULL,
  duration_days REAL NOT NULL, price_per_person_vnd INTEGER NOT NULL, slots_left INTEGER NOT NULL,
  rating REAL NOT NULL, highlights TEXT NOT NULL DEFAULT '[]', highlights_norm TEXT NOT NULL DEFAULT '',
  departs_on TEXT, deeplink TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tours_city ON tours(city_norm);

CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, pw_hash TEXT NOT NULL, salt TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory (
  username TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (username, key)
);
CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY, username TEXT NOT NULL, status TEXT NOT NULL, total_vnd INTEGER NOT NULL,
  created_at TEXT NOT NULL, confirmed_at TEXT
);
CREATE TABLE IF NOT EXISTS order_items (
  order_id TEXT NOT NULL REFERENCES orders(id), ref_id TEXT NOT NULL, kind TEXT NOT NULL,
  title TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price_vnd INTEGER NOT NULL, deeplink TEXT
);
CREATE TABLE IF NOT EXISTS trips (
  id TEXT PRIMARY KEY, username TEXT NOT NULL, name TEXT NOT NULL, budget_vnd INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trips_user ON trips(username, created_at);
CREATE TABLE IF NOT EXISTS expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT NOT NULL REFERENCES trips(id), username TEXT NOT NULL,
  label TEXT NOT NULL, amount_vnd INTEGER NOT NULL, category TEXT NOT NULL, paid_by TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expenses_trip ON expenses(trip_id);
CREATE TABLE IF NOT EXISTS conversations (
  username TEXT NOT NULL, session_id TEXT NOT NULL, history TEXT NOT NULL, seen_refs TEXT NOT NULL,
  display TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (username, session_id)
);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(username, updated_at);
CREATE TABLE IF NOT EXISTS cost_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, day TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL, cost_usd REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cost_day ON cost_log(day, username);
"""

CATALOG_TABLES = ("events", "transport", "lodging", "tours")
MIGRATIONS = [
    ("orders", "trip_id", "TEXT"),
    ("order_items", "when_at", "TEXT"),
]


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            if path != ":memory:":
                c.execute("PRAGMA journal_mode = WAL")  # đọc và ghi đồng thời không chặn nhau, bền hơn khi mất điện
            c.executescript(SCHEMA)
            # Di trú nhẹ cho DB tạo từ phiên bản cũ: thêm cột còn thiếu, không mất dữ liệu.
            for table, column, decl in MIGRATIONS:
                cols = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA synchronous = NORMAL")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()
