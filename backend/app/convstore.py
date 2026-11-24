"""Lưu hội thoại theo người dùng để không mất khi tải lại trang hoặc khởi động lại máy chủ.

Lưu 3 thứ: lịch sử gửi cho LLM (chỉ chữ, không có ảnh), các mã đã hiển thị, và các tin nhắn hiển thị cho giao diện.
Ảnh người dùng không bao giờ được lưu.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .db import Database

MAX_DISPLAY = 60
MAX_HISTORY = 20
MAX_JSON_CHARS = 400_000


def save(db: Database, username: str, sid: str, history: list[dict], seen_refs: set[str], display: list[dict]) -> None:
    history, display = history[-MAX_HISTORY:], display[-MAX_DISPLAY:]
    h, s, d = (json.dumps(x, ensure_ascii=False) for x in (history, sorted(seen_refs), display))
    if len(h) + len(d) > MAX_JSON_CHARS:  # chặn phình to bất thường, giữ phần mới nhất
        display = display[-10:]
        d = json.dumps(display, ensure_ascii=False)
    with db.conn() as c:
        c.execute(
            "INSERT INTO conversations(username, session_id, history, seen_refs, display, updated_at) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(username, session_id) DO UPDATE SET history=excluded.history, seen_refs=excluded.seen_refs, "
            "display=excluded.display, updated_at=excluded.updated_at",
            (username, sid, h, s, d, datetime.now(timezone.utc).isoformat()),
        )


def load(db: Database, username: str, sid: str) -> dict | None:
    with db.conn() as c:
        row = c.execute("SELECT * FROM conversations WHERE username = ? AND session_id = ?", (username, sid)).fetchone()
    if not row:
        return None
    return {"history": json.loads(row["history"]), "seen_refs": set(json.loads(row["seen_refs"])),
            "display": json.loads(row["display"])}


def latest(db: Database, username: str) -> tuple[str, list[dict]] | None:
    with db.conn() as c:
        row = c.execute("SELECT session_id, display FROM conversations WHERE username = ? ORDER BY updated_at DESC LIMIT 1",
                        (username,)).fetchone()
    return (row["session_id"], json.loads(row["display"])) if row else None


def display_from_events(text: str, events: list[dict], has_image: bool) -> list[dict]:
    """Dựng hai tin nhắn hiển thị (người dùng, trợ lý) từ luồng sự kiện của một lượt."""
    body = "".join(e["text"] for e in events if e["type"] == "text_delta")
    blocks = [e["block"] for e in events if e["type"] == "ui_block"]
    errors = [e["message"] for e in events if e["type"] == "error"]
    assistant: dict = {"role": "assistant", "text": body, "blocks": blocks}
    if errors:
        assistant["error"] = errors[0]
    user: dict = {"role": "user", "text": text}
    if has_image:
        user["has_image"] = True
    return [user, assistant]
