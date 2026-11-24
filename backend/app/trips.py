"""Ngân sách chuyến đi và chi tiêu thủ công. Mọi con số do SQL và code tính, LLM chỉ diễn giải.

Chi tiêu của một chuyến = đơn ĐÃ XÁC NHẬN gắn với chuyến + các khoản người dùng tự ghi. Đơn nháp không tính.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime

from .db import Database
from .seed import now_ict
from .textutil import norm

MAX_TRIPS = 20
MAX_EXPENSES_PER_TRIP = 200
MAX_AMOUNT = 10_000_000_000
EXPENSE_CATEGORIES = {
    "transport": "Di chuyển", "lodging": "Lưu trú", "food": "Ăn uống", "activity": "Hoạt động",
    "shopping": "Mua sắm", "other": "Khác",
}
ORDER_KIND_LABEL = {"transport": "Di chuyển", "lodging": "Lưu trú", "event": "Giải trí", "tour": "Tour"}
WARN_PERCENT = 80.0


class TripError(ValueError):
    pass


def _amount(value, name: str = "Số tiền") -> int:
    try:
        v = int(value)
    except (TypeError, ValueError) as exc:
        raise TripError(f"{name} phải là số nguyên (VND)") from exc
    if not 1 <= v <= MAX_AMOUNT:
        raise TripError(f"{name} phải từ 1 đến {MAX_AMOUNT:,}".replace(",", "."))
    return v


def _text(value, name: str, max_len: int) -> str:
    s = re.sub(r"\s+", " ", str(value or "")).strip()
    if not s:
        raise TripError(f"{name} không được để trống")
    if len(s) > max_len:
        raise TripError(f"{name} tối đa {max_len} ký tự")
    return s


def create_trip(db: Database, username: str, name: str, budget_vnd) -> dict:
    name, budget = _text(name, "Tên chuyến đi", 60), _amount(budget_vnd, "Ngân sách")
    with db.conn() as c:
        if c.execute("SELECT COUNT(*) FROM trips WHERE username = ?", (username,)).fetchone()[0] >= MAX_TRIPS:
            raise TripError(f"Tối đa {MAX_TRIPS} chuyến đi")
        existing = [r["name"] for r in c.execute("SELECT name FROM trips WHERE username = ?", (username,))]
        if any(norm(n) == norm(name) for n in existing):
            raise TripError("Đã có chuyến đi trùng tên, hãy dùng tên khác hoặc cập nhật chuyến đó")
        trip_id = "trip_" + secrets.token_hex(4)
        c.execute("INSERT INTO trips(id, username, name, budget_vnd, created_at) VALUES (?,?,?,?,?)",
                  (trip_id, username, name, budget, now_ict().isoformat()))
    return {"id": trip_id, "name": name, "budget_vnd": budget}


def resolve_trip(db: Database, username: str, ref: str | None) -> dict:
    """Tìm chuyến theo mã hoặc tên (không phân biệt dấu, hoa thường). Không nêu thì lấy chuyến mới nhất."""
    with db.conn() as c:
        rows = c.execute("SELECT * FROM trips WHERE username = ? ORDER BY created_at DESC, rowid DESC", (username,)).fetchall()
    if not rows:
        raise TripError("Bạn chưa có chuyến đi nào. Hãy tạo chuyến đi và ngân sách trước")
    if not ref:
        return dict(rows[0])
    n = norm(ref)
    for r in rows:
        if r["id"] == ref or norm(r["name"]) == n:
            return dict(r)
    partial = [r for r in rows if n and n in norm(r["name"])]
    if len(partial) == 1:
        return dict(partial[0])
    if len(partial) > 1:
        raise TripError("Có nhiều chuyến đi khớp tên này: " + ", ".join(r["name"] for r in partial))
    raise TripError("Không tìm thấy chuyến đi. Các chuyến hiện có: " + ", ".join(r["name"] for r in rows))


def list_trips(db: Database, username: str) -> list[dict]:
    with db.conn() as c:
        rows = c.execute("SELECT id, name, budget_vnd FROM trips WHERE username = ? ORDER BY created_at DESC, rowid DESC", (username,)).fetchall()
    return [dict(r) for r in rows]


def set_budget(db: Database, username: str, ref: str | None, budget_vnd) -> dict:
    trip = resolve_trip(db, username, ref)
    budget = _amount(budget_vnd, "Ngân sách")
    with db.conn() as c:
        c.execute("UPDATE trips SET budget_vnd = ? WHERE id = ? AND username = ?", (budget, trip["id"], username))
    return {**trip, "budget_vnd": budget}


def add_expense(db: Database, username: str, ref: str | None, label: str, amount_vnd, category: str | None = None,
                paid_by: str | None = None) -> dict:
    trip = resolve_trip(db, username, ref)
    label, amount = _text(label, "Nội dung khoản chi", 80), _amount(amount_vnd)
    category = (category or "other").lower()
    if category not in EXPENSE_CATEGORIES:
        raise TripError("category phải là một trong: " + ", ".join(EXPENSE_CATEGORIES))
    payer = _text(paid_by, "Người trả", 30) if paid_by else None
    with db.conn() as c:
        if c.execute("SELECT COUNT(*) FROM expenses WHERE trip_id = ?", (trip["id"],)).fetchone()[0] >= MAX_EXPENSES_PER_TRIP:
            raise TripError(f"Mỗi chuyến tối đa {MAX_EXPENSES_PER_TRIP} khoản chi")
        c.execute("INSERT INTO expenses(trip_id, username, label, amount_vnd, category, paid_by, created_at) VALUES (?,?,?,?,?,?,?)",
                  (trip["id"], username, label, amount, category, payer, now_ict().isoformat()))
    return {"trip": trip["name"], "label": label, "amount_vnd": amount, "category": EXPENSE_CATEGORIES[category]}


def status(db: Database, username: str, ref: str | None = None) -> dict:
    trip = resolve_trip(db, username, ref)
    with db.conn() as c:
        order_rows = c.execute(
            "SELECT i.kind AS kind, SUM(i.quantity * i.unit_price_vnd) AS amount FROM order_items i "
            "JOIN orders o ON o.id = i.order_id WHERE o.username = ? AND o.trip_id = ? AND o.status = 'confirmed' GROUP BY i.kind",
            (username, trip["id"])).fetchall()
        exp_rows = c.execute("SELECT category, SUM(amount_vnd) AS amount FROM expenses WHERE trip_id = ? AND username = ? GROUP BY category",
                             (trip["id"], username)).fetchall()
        pending = c.execute(
            "SELECT COALESCE(SUM(total_vnd), 0) FROM orders WHERE username = ? AND trip_id = ? AND status = 'draft' AND created_at >= ?",
            (username, trip["id"], _draft_cutoff())).fetchone()[0]
    parts: dict[str, int] = {}
    orders_total = 0
    for r in order_rows:
        parts[ORDER_KIND_LABEL.get(r["kind"], r["kind"])] = parts.get(ORDER_KIND_LABEL.get(r["kind"], r["kind"]), 0) + r["amount"]
        orders_total += r["amount"]
    manual_total = 0
    for r in exp_rows:
        label = EXPENSE_CATEGORIES.get(r["category"], "Khác")
        parts[label] = parts.get(label, 0) + r["amount"]
        manual_total += r["amount"]
    spent = orders_total + manual_total
    budget = trip["budget_vnd"]
    percent = round(100 * spent / budget, 1)
    # So sánh bằng số nguyên: 799.999/1.000.000 làm tròn thành 80,0% nhưng chưa chạm ngưỡng cảnh báo.
    level = "over" if spent > budget else "warning" if spent * 100 >= WARN_PERCENT * budget else "ok"
    return {
        "trip_id": trip["id"], "trip": trip["name"], "budget_vnd": budget, "spent_vnd": spent,
        "orders_vnd": orders_total, "manual_vnd": manual_total, "remaining_vnd": budget - spent, "percent": percent,
        "level": level, "pending_drafts_vnd": pending,
        "breakdown": [{"label": k, "amount_vnd": v} for k, v in sorted(parts.items(), key=lambda kv: -kv[1])],
    }


def _draft_cutoff() -> str:
    from .orders import DRAFT_TTL

    return (now_ict() - DRAFT_TTL).isoformat()


def status_block(s: dict) -> dict:
    return {"kind": "budget_status", "trip": s["trip"], "budget_vnd": s["budget_vnd"], "spent_vnd": s["spent_vnd"],
            "remaining_vnd": s["remaining_vnd"], "percent": s["percent"], "level": s["level"], "breakdown": s["breakdown"]}
