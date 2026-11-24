"""Bộ nhớ sở thích theo người dùng. Chỉ nhận khóa trong danh sách cho phép, từ chối dữ liệu nhạy cảm."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .db import Database

ALLOWED_KEYS = {
    "home_city": "Thành phố xuất phát",
    "budget_vnd": "Ngân sách thường dùng (VND)",
    "preferred_carrier": "Hãng hoặc loại phương tiện ưa thích",
    "lodging_amenities": "Tiện nghi lưu trú ưa thích",
    "interests": "Sở thích giải trí",
    "seat_class": "Hạng ghế ưa thích",
    "party_size": "Số người đi cùng thường gặp",
}
MAX_VALUE_LEN = 120
MAX_KEYS = len(ALLOWED_KEYS)

_SENSITIVE = [
    re.compile(r"\d[\d\s.\-]{8,}\d"),  # chuỗi số dài: thẻ, CCCD, số điện thoại
    re.compile(r"\b(cvv|cvc|otp|mật khẩu|mat khau|password|passcode)\b", re.I),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),  # email
]


class MemoryValidationError(ValueError):
    pass


def validate(key: str, value: str) -> str:
    if key not in ALLOWED_KEYS:
        raise MemoryValidationError("Khóa không hợp lệ. Khóa cho phép: " + ", ".join(ALLOWED_KEYS))
    value = (value or "").strip()
    if not value:
        raise MemoryValidationError("Giá trị không được rỗng")
    if len(value) > MAX_VALUE_LEN:
        raise MemoryValidationError(f"Giá trị tối đa {MAX_VALUE_LEN} ký tự")
    if any(p.search(value) for p in _SENSITIVE):
        raise MemoryValidationError("Không lưu dữ liệu nhạy cảm (số thẻ, CCCD, số điện thoại, email, mật khẩu, OTP)")
    return value


def save(db: Database, username: str, key: str, value: str) -> None:
    value = validate(key, value)
    with db.conn() as c:
        c.execute(
            "INSERT INTO memory(username, key, value, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(username, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (username, key, value, datetime.now(timezone.utc).isoformat()),
        )


def recall(db: Database, username: str) -> dict[str, str]:
    with db.conn() as c:
        rows = c.execute("SELECT key, value FROM memory WHERE username = ? ORDER BY key", (username,)).fetchall()
    return {r["key"]: r["value"] for r in rows}


def delete(db: Database, username: str, key: str) -> bool:
    with db.conn() as c:
        return c.execute("DELETE FROM memory WHERE username = ? AND key = ?", (username, key)).rowcount > 0


def clear(db: Database, username: str) -> int:
    with db.conn() as c:
        return c.execute("DELETE FROM memory WHERE username = ?", (username,)).rowcount
