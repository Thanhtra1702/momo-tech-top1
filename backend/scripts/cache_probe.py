"""Đo tỷ lệ cache hit của DeepSeek với đúng system prompt và danh sách công cụ của ứng dụng.

Chạy:  python scripts/cache_probe.py        (từ thư mục backend, cần LLM_API_KEY trong .env)
Chi phí rất nhỏ (vài nghìn token). In prompt_cache_hit_tokens và prompt_cache_miss_tokens của từng yêu cầu.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from openai import OpenAI  # noqa: E402

from app import catalog  # noqa: E402
from app.agent import build_system_prompt  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.llm import request_options  # noqa: E402
from app.seed import ensure_seeded  # noqa: E402
from app.tools import TOOL_SPECS, ToolContext, run_tool  # noqa: E402

import tempfile  # noqa: E402


def usage_of(resp) -> tuple[int, int, int]:
    u = resp.usage
    hit = getattr(u, "prompt_cache_hit_tokens", None)
    miss = getattr(u, "prompt_cache_miss_tokens", None)
    if hit is None and getattr(u, "model_extra", None):
        hit, miss = u.model_extra.get("prompt_cache_hit_tokens"), u.model_extra.get("prompt_cache_miss_tokens")
    return u.prompt_tokens, hit or 0, miss or 0


def main() -> int:
    s = Settings.from_env()
    client = OpenAI(api_key=s.llm_api_key, base_url=s.llm_base_url, timeout=60)
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "p.db"))
        ensure_seeded(db)
        system = build_system_prompt(db, "probe", "fast")
        tools_chars = len(json.dumps(TOOL_SPECS, ensure_ascii=False))
        print(f"system prompt: {len(system)} ký tự, tools: {tools_chars} ký tự")

        def call(messages, label, mode="fast"):
            r = client.chat.completions.create(model=s.llm_model, messages=messages, tools=TOOL_SPECS, max_tokens=60,
                                               **{k: v for k, v in request_options(mode).items() if k != "max_tokens"})
            total, hit, miss = usage_of(r)
            print(f"{label:<44} prompt={total:>5} hit={hit:>5} miss={miss:>5} ({100 * hit / max(total, 1):.0f}% hit)")
            return r

        msgs = lambda q: [{"role": "system", "content": system}, {"role": "user", "content": q}]
        for i, q in enumerate(["Xin chào", "Tìm vé phim ở Hà Nội", "Thời tiết Huế ngày mai", "Có concert nào ở Đà Nẵng?"], 1):
            call(msgs(q), f"{i}. phiên mới, câu khác nhau: {q[:22]}")
            time.sleep(3)

        # Một vòng agent thật: bước 1 gọi công cụ, bước 2 gửi kết quả. Bước 2 nên hit phần lớn bước 1.
        ctx = ToolContext(db=db, username="probe")
        base = msgs("Tìm vé phim ở Sài Gòn dưới 150 nghìn")
        r1 = call(base, "5. vòng agent, bước 1")
        m = r1.choices[0].message
        if m.tool_calls:
            tool_msgs = [{"role": "tool", "tool_call_id": tc.id, "content": run_tool(ctx, tc.function.name, tc.function.arguments)[0]}
                         for tc in m.tool_calls]
            time.sleep(3)
            call(base + [m.model_dump(exclude_none=True)] + tool_msgs, "6. vòng agent, bước 2 (có kết quả công cụ)")
        time.sleep(3)
        call(msgs("Tìm vé phim ở Hà Nội cuối tuần"), "7. phiên mới sau khi đã có nhiều yêu cầu")
        print("\nĐộ trễ xây cache: cùng một yêu cầu bước 2, gửi ngay và gửi lại sau khi chờ")
        base2 = msgs("Tìm chuyến bay Hà Nội đi Huế rẻ nhất")
        r1 = call(base2, "10. bước 1 (mới)")
        m = r1.choices[0].message
        if m.tool_calls:
            tool_msgs = [{"role": "tool", "tool_call_id": tc.id, "content": run_tool(ctx, tc.function.name, tc.function.arguments)[0]}
                         for tc in m.tool_calls]
            step2 = base2 + [m.model_dump(exclude_none=True)] + tool_msgs
            call(step2, "11. bước 2 gửi NGAY sau bước 1")
            for wait in (2, 8, 20):
                time.sleep(wait)
                call(step2, f"12. bước 2 gửi lại sau thêm {wait}s")
        print("\nChế độ sâu (system prompt có thêm đoạn DEEP_NOTE ở cuối):")
        deep_system = build_system_prompt(db, "probe", "deep")
        call([{"role": "system", "content": deep_system}, {"role": "user", "content": "Xin chào"}], "8. deep, phiên mới", "deep")
        time.sleep(3)
        call([{"role": "system", "content": deep_system}, {"role": "user", "content": "Tìm vé phim ở Huế"}], "9. deep, phiên mới khác", "deep")
    return 0


if __name__ == "__main__":
    sys.exit(main())
