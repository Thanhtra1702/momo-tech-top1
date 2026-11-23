"""Small SQLite repository using only the Python standard library."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from backend.data.seed import build_catalog

DEFAULT_DB = Path(os.getenv("MOMO_DB_PATH", "./momo_demo.sqlite3"))


class CatalogRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB):
        self.db_path = str(db_path)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS listings (id TEXT PRIMARY KEY, product_id TEXT, category TEXT, product_name TEXT, price_vnd INTEGER, seller_id TEXT, seller_name TEXT, seller_age_days INTEGER, completed_orders INTEGER, rating REAL, review_count INTEGER, repetitive_reviews INTEGER, payment_channel TEXT, payee_name TEXT, description TEXT, scam_label INTEGER, scam_type TEXT, synthetic INTEGER, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, listing_id TEXT NOT NULL, status TEXT NOT NULL, second_confirmation INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, payload TEXT NOT NULL)")
            existing = db.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            if existing == 0:
                rows = build_catalog()
                db.executemany(
                    "INSERT INTO listings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(
                        x["id"], x["product_id"], x["category"], x["product_name"], x["price_vnd"],
                        x["seller_id"], x["seller_name"], x["seller_age_days"], x["completed_orders"],
                        x["rating"], x["review_count"], int(x["repetitive_reviews"]), x["payment_channel"],
                        x["payee_name"], x["description"], int(x["scam_label"]), x["scam_type"], 1,
                        json.dumps(x, ensure_ascii=False),
                    ) for x in rows],
                )

    def listing(self, listing_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM listings WHERE id=?", (listing_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def all_listings(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM listings ORDER BY id").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def create_order(self, order: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO orders VALUES (?,?,?,?,?,?)", (
                order["id"], order["listing_id"], order["status"], int(order["second_confirmation"]),
                order["created_at"], json.dumps(order, ensure_ascii=False),
            ))

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM orders WHERE id=?", (order_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def update_order(self, order: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute("UPDATE orders SET status=?, second_confirmation=?, payload=? WHERE id=?", (
                order["status"], int(order["second_confirmation"]), json.dumps(order, ensure_ascii=False), order["id"],
            ))\n