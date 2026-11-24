"""Thử tải với DeepSeek thật: nhiều phiên chạy song song, mỗi phiên đi hết luồng tìm vé, chọn, xác nhận.

    python scripts/load_test.py --url http://127.0.0.1:8000 --sessions 8 --users demo1:momo2026,demo2:momo2026

Tốn tiền thật (khoảng 0,003 USD mỗi lượt). Mỗi người dùng bị giới hạn tần suất theo RATE_LIMIT_PER_MIN.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

sys.stdout.reconfigure(encoding="utf-8")


def chat(client: httpx.Client, token: str, sid: str, message: str) -> tuple[list[dict], float]:
    t0 = time.perf_counter()
    events: list[dict] = []
    with client.stream("POST", "/chat", headers={"Authorization": f"Bearer {token}"},
                       json={"message": message, "session_id": sid, "mode": "fast"}, timeout=120) as r:
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.read().decode()[:120]}")
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events, time.perf_counter() - t0


def scenario(url: str, user: str, password: str, n: int) -> dict:
    out = {"session": n, "user": user, "turns": [], "error": None, "confirmed": False}
    sid = f"load-{uuid.uuid4().hex[:12]}"
    try:
        with httpx.Client(base_url=url, timeout=30) as c:
            token = c.post("/auth/login", json={"username": user, "password": password}).json()["token"]
            ev, dt = chat(c, token, sid, "Tìm chuyến bay Hà Nội đi Đà Nẵng, rẻ nhất, thứ Sáu tuần sau")
            out["turns"].append(dt)
            if any(e["type"] == "error" for e in ev):
                raise RuntimeError("lượt 1 có lỗi: " + str([e for e in ev if e["type"] == "error"][0]))
            if not any(e["type"] == "ui_block" for e in ev):
                raise RuntimeError("lượt 1 không có thẻ vé")
            ev, dt = chat(c, token, sid, "Chọn chuyến đầu tiên, đặt 1 vé")
            out["turns"].append(dt)
            draft = next((e["block"] for e in ev if e["type"] == "ui_block" and e["block"]["kind"] == "order_draft"), None)
            if not draft:
                raise RuntimeError("lượt 2 không tạo được đơn nháp")
            r = c.post(f"/orders/{draft['order_id']}/confirm", headers={"Authorization": f"Bearer {token}"})
            out["confirmed"] = r.status_code in (200, 409)  # 409 hợp lệ nếu chuyến vừa hết chỗ
            ev, dt = chat(c, token, sid, "Cảm ơn, thời tiết Đà Nẵng cuối tuần sao?")
            out["turns"].append(dt)
            if any(e["type"] == "error" for e in ev):
                raise RuntimeError("lượt 3 có lỗi")
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--sessions", type=int, default=8)
    ap.add_argument("--users", default="demo1:momo2026,demo2:momo2026,demo3:momo2026")
    args = ap.parse_args()
    users = [u.split(":", 1) for u in args.users.split(",")]
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.sessions) as pool:
        results = list(pool.map(lambda i: scenario(args.url, *users[i % len(users)], i), range(args.sessions)))
    wall = time.perf_counter() - t0
    turns = sorted(t for r in results for t in r["turns"])
    ok = [r for r in results if not r["error"]]
    print(f"{len(ok)}/{len(results)} phiên chạy hết luồng, tổng {wall:.1f}s")
    if turns:
        p95 = turns[min(len(turns) - 1, int(0.95 * len(turns)))]
        print(f"{len(turns)} lượt chat: TB {statistics.mean(turns):.1f}s, p50 {statistics.median(turns):.1f}s, p95 {p95:.1f}s, tối đa {max(turns):.1f}s")
    for r in results:
        if r["error"]:
            print(f"  phiên {r['session']} ({r['user']}): {r['error']}")
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
