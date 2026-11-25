"""Đơn nháp và xác nhận mô phỏng.

Agent chỉ gọi create_draft. Chỉ endpoint do người dùng bấm mới gọi confirm.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from . import catalog
from .catalog import KINDS
from .db import Database
from .seed import now_ict

MAX_ITEMS = 5
MAX_QTY = 10
DRAFT_TTL = timedelta(minutes=30)


class OrderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code  # not_found | invalid | conflict
        self.message = message


def _required_stock(kind: str, quantity: int) -> int:
    # Lưu trú: quantity là số đêm, mỗi đêm cần 1 phòng trống. Các loại khác cần đủ số lượng.
    return 1 if kind == "lodging" else quantity


_WHEN_FIELD = {"event": "starts_at", "transport": "departs_at", "tour": "departs_on"}


def _same_listing_snapshot(item: dict, row) -> bool:
    """A reused catalog ID must still describe the exact item shown in the draft."""
    kind = item["kind"]
    if kind == "event":
        title = row["title"]
    elif kind == "transport":
        title = f"{row['carrier']}: {row['origin']} - {row['destination']}"
    else:
        title = row["name"]
    when = row[_WHEN_FIELD[kind]] if kind in _WHEN_FIELD else None
    if kind == "tour" and when:
        when = f"{when}T00:00:00+07:00"
    return title == item["title"] and when == item["when_at"] and row["deeplink"] == item["deeplink"]


def create_draft(db: Database, username: str, items: list[dict], trip_id: str | None = None) -> dict:
    if not isinstance(items, list) or not items:
        raise OrderError("invalid", "Cần ít nhất một mục")
    if len(items) > MAX_ITEMS:
        raise OrderError("invalid", f"Tối đa {MAX_ITEMS} mục mỗi đơn")
    if trip_id is not None:
        with db.conn() as c:
            if not c.execute("SELECT 1 FROM trips WHERE id = ? AND username = ?", (trip_id, username)).fetchone():
                raise OrderError("not_found", "Không tìm thấy chuyến đi này")
    lines = []
    for it in items:
        ref_id = str(it.get("ref_id", ""))
        try:
            qty = int(it.get("quantity", 1))
        except (TypeError, ValueError) as exc:
            raise OrderError("invalid", "quantity phải là số nguyên") from exc
        if not 1 <= qty <= MAX_QTY:
            raise OrderError("invalid", f"quantity phải từ 1 đến {MAX_QTY}")
        found = catalog.get_item(db, ref_id)
        if not found:
            raise OrderError("not_found", f"Không tìm thấy mục {ref_id}")
        kind, item = found
        price, stock, title = catalog.unit_price_and_stock(item, kind)
        if stock < _required_stock(kind, qty):
            raise OrderError("conflict", f"{title} không còn đủ chỗ")
        when_at = item.get(_WHEN_FIELD[kind]) if kind in _WHEN_FIELD else None
        if kind == "tour" and when_at:  # tour chỉ có ngày khởi hành: đổi sang date-time đầu ngày giờ Việt Nam
            when_at = f"{when_at}T00:00:00+07:00"
        lines.append((ref_id, kind, title, qty, price, item["deeplink"], when_at))
    total = sum(q * p for _, _, _, q, p, _, _ in lines)
    order_id = "ord_" + secrets.token_hex(4)
    created = now_ict().isoformat()
    with db.conn() as c:
        c.execute("INSERT INTO orders(id, username, status, total_vnd, created_at, confirmed_at, trip_id) VALUES (?,?,?,?,?,NULL,?)",
                  (order_id, username, "draft", total, created, trip_id))
        c.executemany("INSERT INTO order_items(order_id, ref_id, kind, title, quantity, unit_price_vnd, deeplink, when_at) "
                      "VALUES (?,?,?,?,?,?,?,?)", [(order_id, *line) for line in lines])
    return get_order(db, username, order_id)


def get_order(db: Database, username: str, order_id: str) -> dict:
    with db.conn() as c:
        o = c.execute("SELECT * FROM orders WHERE id = ? AND username = ?", (order_id, username)).fetchone()
        if not o:
            raise OrderError("not_found", "Không tìm thấy đơn")
        rows = c.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    return _order_dict(o, rows)


def _order_dict(o, rows) -> dict:
    status = o["status"]
    if status == "draft" and now_ict() - datetime.fromisoformat(o["created_at"]) > DRAFT_TTL:
        status = "expired"
    return {
        "id": o["id"], "status": status, "trip_id": o["trip_id"],
        "expires_at": (datetime.fromisoformat(o["created_at"]) + DRAFT_TTL).isoformat() if o["status"] == "draft" else None,
        "items": [{"ref_id": r["ref_id"], "kind": r["kind"], "title": r["title"], "quantity": r["quantity"],
                   "unit_price_vnd": r["unit_price_vnd"], "deeplink": r["deeplink"], "when_at": r["when_at"]} for r in rows],
        "total_vnd": o["total_vnd"], "created_at": o["created_at"], "confirmed_at": o["confirmed_at"],
    }


def list_orders(db: Database, username: str, limit: int = 50) -> list[dict]:
    """Đơn của một người dùng, mới nhất trước. Chỉ đọc đúng dữ liệu của người đó."""
    with db.conn() as c:
        orders_rows = c.execute("SELECT * FROM orders WHERE username = ? ORDER BY created_at DESC LIMIT ?", (username, limit)).fetchall()
        ids = [o["id"] for o in orders_rows]
        items = c.execute(f"SELECT * FROM order_items WHERE order_id IN ({','.join('?' * len(ids))})", ids).fetchall() if ids else []
    by_order: dict[str, list] = {}
    for r in items:
        by_order.setdefault(r["order_id"], []).append(r)
    return [_order_dict(o, by_order.get(o["id"], [])) for o in orders_rows]


def upcoming(db: Database, username: str, within_days: int | None = None) -> list[dict]:
    """Các mục của đơn đã xác nhận có thời điểm trong tương lai, sớm nhất trước."""
    now = now_ict().isoformat()
    out = []
    for order in list_orders(db, username):
        if order["status"] != "confirmed":
            continue
        for it in order["items"]:
            when = it.get("when_at")
            if when and when >= now:
                out.append({"order_id": order["id"], "ref_id": it["ref_id"], "kind": it["kind"], "title": it["title"],
                            "quantity": it["quantity"], "when_at": when})
    out.sort(key=lambda x: x["when_at"])
    if within_days is not None:
        limit = (now_ict() + timedelta(days=within_days)).isoformat()
        out = [x for x in out if x["when_at"] <= limit]
    return out


def confirm(db: Database, username: str, order_id: str) -> dict:
    """Xác nhận mô phỏng sau khi kiểm tra lại danh tính mục, giá và tồn kho."""
    order = get_order(db, username, order_id)
    if order["status"] == "confirmed":
        return order
    if order["status"] == "expired":
        raise OrderError("conflict", "Đơn nháp đã hết hạn, hãy tạo lại")
    if order["status"] != "draft":
        raise OrderError("conflict", "Đơn không ở trạng thái có thể xác nhận")
    with db.conn() as c:
        c.execute("BEGIN IMMEDIATE")
        for it in order["items"]:
            kind = it["kind"]
            table, _, price_col, stock_col = KINDS[kind]
            row = c.execute(f"SELECT * FROM {table} WHERE id = ?", (it["ref_id"],)).fetchone()
            if not row:
                raise OrderError("conflict", f"{it['title']} không còn tồn tại")
            if not _same_listing_snapshot(it, row):
                raise OrderError("conflict", f"Thông tin của {it['title']} đã thay đổi, hãy tạo lại đơn")
            if row[price_col] != it["unit_price_vnd"]:
                raise OrderError("conflict", f"Giá của {it['title']} đã thay đổi, hãy tạo lại đơn")
            if row[stock_col] < _required_stock(kind, it["quantity"]):
                raise OrderError("conflict", f"{it['title']} đã hết chỗ")
        for it in order["items"]:
            table, _, _, stock_col = KINDS[it["kind"]]
            c.execute(f"UPDATE {table} SET {stock_col} = {stock_col} - ? WHERE id = ?",
                      (_required_stock(it["kind"], it["quantity"]), it["ref_id"]))
        c.execute("UPDATE orders SET status='confirmed', confirmed_at=? WHERE id=? AND username=? AND status='draft'",
                  (now_ict().isoformat(), order_id, username))
    return get_order(db, username, order_id)
