"""Server phát triển dùng LLM giả theo luật, để thử giao diện khi chưa có khóa DeepSeek.

Chạy:  python scripts/dev_server.py        (từ thư mục backend, cổng 8000)
KHÔNG dùng cho sản phẩm thật. Nó chỉ hiểu vài mẫu câu đơn giản.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402

from app.config import Settings  # noqa: E402
from app.llm import AssistantTurn, FakeLLMClient, ToolCall  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import now_ict  # noqa: E402


def _call(name: str, args: dict, n: int) -> AssistantTurn:
    return AssistantTurn(tool_calls=[ToolCall(f"dev{n}", name, json.dumps(args, ensure_ascii=False))])


class RuleLLM(FakeLLMClient):
    def stream(self, messages, tools=None, mode="fast"):
        last = messages[-1]
        if last["role"] == "tool":
            self._script = [AssistantTurn(text="Mình đã tìm xong, **bạn xem** các gợi ý ở trên nhé.\n\n- Gợi ý một\n- Gợi ý hai\n\n(LLM giả để thử giao diện)")]
        else:
            content = last["content"] if isinstance(last["content"], str) else last["content"][0]["text"]
            low = content.lower()
            ref = re.search(r"\b(?:evt|trp|lod|tur)_[a-z0-9_]+\b", content)
            start = (now_ict().date().toordinal() + 10)
            from datetime import date
            start_s = date.fromordinal(start).isoformat()
            if ref and "đơn" in low:
                qty = int((re.search(r"số lượng (\d+)", low) or [0, 1])[1])
                self._script = [_call("create_order_draft", {"items": [{"ref_id": ref.group(0), "quantity": qty}]}, 1)]
            elif "lịch trình" in low or "kế hoạch" in low:
                self._script = [_call("build_itinerary", {"city": "Đà Lạt", "days": 3, "budget_vnd": 8_000_000, "guests": 2,
                                                          "start_date": start_s, "origin": "Hà Nội"}, 2)]
            elif "kiểm tra" in low and ("tin nhắn" in low or "link" in low):
                self._script = [_call("check_scam", {"text": content.split(":", 1)[-1].strip()}, 6)]
            elif "tạo chuyến đi" in low:
                self._script = [_call("create_trip", {"name": "Đà Lạt tháng 12", "budget_vnd": 8_000_000}, 7)]
            elif "ghi" in low and "khoản chi" in low:
                self._script = [_call("add_expense", {"label": "Ăn tối", "amount_vnd": 450_000, "category": "food"}, 8)]
            elif "chia tiền" in low:
                self._script = [_call("split_bill", {"total_vnd": 3_000_000, "people": ["An", "Bình", "Chi"], "payer": "An", "label": "tiền khách sạn"}, 9)]
            elif "đơn của tôi" in low:
                self._script = [_call("get_my_orders", {}, 10)]
            elif "phim" in low or "concert" in low:
                self._script = [_call("search_events", {"kind": "concert" if "concert" in low else "movie", "limit": 4}, 3)]
            elif "bay" in low or "vé" in low:
                self._script = [_call("search_transport", {"origin": "Hà Nội", "destination": "Đà Nẵng", "mode": "flight", "limit": 4}, 4)]
            elif "khách sạn" in low or "lưu trú" in low:
                self._script = [_call("search_lodging", {"city": "Đà Lạt", "amenities": ["hồ bơi"], "limit": 4}, 5)]
            else:
                self._script = [AssistantTurn(text="Mình hỗ trợ đặt vé, du lịch và giải trí. (LLM giả để thử giao diện)")]
        yield from super().stream(messages, tools, mode)


if __name__ == "__main__":
    settings = Settings.from_env().with_overrides(frontend_dir=str(Path(__file__).resolve().parents[2] / "frontend" / "dist"),
                                                  db_path="data/dev.db")
    uvicorn.run(create_app(settings, llm_factory=RuleLLM), host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
