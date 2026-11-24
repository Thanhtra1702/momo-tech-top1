"""Đăng nhập tài khoản demo. Mật khẩu băm bằng PBKDF2, token lưu dạng băm SHA-256."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from .config import Settings
from .db import Database

PBKDF2_ROUNDS = 200_000


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS).hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def parse_demo_users(spec: str) -> dict[str, str]:
    users: dict[str, str] = {}
    for part in spec.split(","):
        if ":" in part:
            name, pw = part.split(":", 1)
            if name.strip() and pw:
                users[name.strip()] = pw
    return users


def ensure_demo_users(db: Database, settings: Settings) -> None:
    with db.conn() as c:
        for name, pw in parse_demo_users(settings.demo_users).items():
            salt = secrets.token_bytes(16)
            c.execute("INSERT INTO users(username, pw_hash, salt) VALUES (?,?,?) "
                      "ON CONFLICT(username) DO UPDATE SET pw_hash=excluded.pw_hash, salt=excluded.salt",
                      (name, _hash(pw, salt), salt.hex()))


def login(db: Database, settings: Settings, username: str, password: str) -> str | None:
    with db.conn() as c:
        row = c.execute("SELECT pw_hash, salt FROM users WHERE username = ?", (username,)).fetchone()
        # Luôn băm một lần để thời gian phản hồi không lộ việc tài khoản có tồn tại hay không.
        salt = bytes.fromhex(row["salt"]) if row else b"\x00" * 16
        candidate = _hash(password, salt)
        if not row or not hmac.compare_digest(candidate, row["pw_hash"]):
            return None
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(seconds=settings.session_ttl_s)
        c.execute("INSERT INTO sessions(token_hash, username, expires_at) VALUES (?,?,?)",
                  (_token_hash(token), username, expires.isoformat()))
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
    return token


def user_for_token(db: Database, token: str) -> str | None:
    with db.conn() as c:
        row = c.execute("SELECT username, expires_at FROM sessions WHERE token_hash = ?", (_token_hash(token),)).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        return None
    return row["username"]
