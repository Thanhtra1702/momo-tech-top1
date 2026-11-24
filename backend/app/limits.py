"""Giới hạn tần suất và trần chi phí theo ngày."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from .config import Settings
from .db import Database
from .seed import now_ict


class LimitError(Exception):
    def __init__(self, message: str, status: int = 429):
        super().__init__(message)
        self.message = message
        self.status = status


class RateLimiter:
    """Cửa sổ trượt trong bộ nhớ, theo khóa (tên người dùng hoặc 'login:<tên>')."""

    def __init__(self, max_per_window: int, window_s: float = 60.0, clock=time.monotonic):
        self._max, self._window, self._clock = max_per_window, window_s, clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = self._clock()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self._window:
                q.popleft()
            if len(q) >= self._max:
                raise LimitError("Bạn gửi quá nhanh, vui lòng thử lại sau ít phút.")
            q.append(now)


class CostGuard:
    def __init__(self, db: Database, settings: Settings):
        self._db, self._s = db, settings

    @staticmethod
    def _today() -> str:
        return now_ict().date().isoformat()

    def spent(self, username: str | None = None) -> float:
        sql, params = "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE day = ?", [self._today()]
        if username:
            sql += " AND username = ?"
            params.append(username)
        with self._db.conn() as c:
            return float(c.execute(sql, params).fetchone()[0])

    def check(self, username: str) -> None:
        if self.spent() >= self._s.daily_cost_cap_usd:
            raise LimitError("Hệ thống đã đạt giới hạn sử dụng trong ngày. Vui lòng quay lại vào ngày mai.", 429)
        if self.spent(username) >= self._s.user_daily_cost_cap_usd:
            raise LimitError("Bạn đã dùng hết hạn mức trong ngày. Vui lòng quay lại vào ngày mai.", 429)

    def record(self, username: str, prompt_tokens: int, completion_tokens: int, cost_usd: float) -> None:
        with self._db.conn() as c:
            c.execute("INSERT INTO cost_log(username, day, prompt_tokens, completion_tokens, cost_usd) VALUES (?,?,?,?,?)",
                      (username, self._today(), prompt_tokens, completion_tokens, cost_usd))

    def report(self) -> dict:
        with self._db.conn() as c:
            rows = c.execute(
                "SELECT username, COUNT(*) AS requests, SUM(prompt_tokens) AS p, SUM(completion_tokens) AS o, SUM(cost_usd) AS usd "
                "FROM cost_log WHERE day = ? GROUP BY username", (self._today(),)).fetchall()
        return {"day": self._today(), "total_usd": round(sum(r["usd"] for r in rows), 6),
                "by_user": [{"username": r["username"], "requests": r["requests"], "prompt_tokens": r["p"],
                             "completion_tokens": r["o"], "cost_usd": round(r["usd"], 6)} for r in rows]}
