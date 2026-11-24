"""Thử nhanh các điểm chưa chắc về DeepSeek (Task 1).

Chạy:  python spike/deepseek_spike.py        (cần LLM_API_KEY trong môi trường)

Kiểm tra 3 việc và in PASS/FAIL cho từng việc:
  1. chat thường, thinking tắt
  2. tool-calls kèm thinking bật, có gửi lại reasoning_content
  3. gửi ảnh (định dạng image_url với data URL) vào deepseek-flash
Kết quả ghi vào docs/deepseek-spike.md để chốt định dạng ở Task 2 và Task 7.
"""

from __future__ import annotations

import base64
import json
import os
import struct
import sys
import zlib

from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import load_dotenv  # noqa: E402


def tiny_png(width: int = 64, height: int = 64, rgb=(220, 30, 30)) -> bytes:
    """PNG đơn sắc tạo bằng thư viện chuẩn, không cần file ảnh."""
    row = b"\x00" + bytes(rgb) * width
    raw = row * height

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    load_dotenv()
    key = os.environ.get("LLM_API_KEY")
    if not key:
        print("Thiếu LLM_API_KEY trong môi trường.")
        return 2
    model = os.environ.get("LLM_MODEL", "deepseek-flash")
    client = OpenAI(
        api_key=key,
        base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
        timeout=90,
    )
    results: dict[str, str] = {}

    # 1. chat thường
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Trả lời đúng một từ: xin chào"}],
            extra_body={"thinking": {"type": "disabled"}},
        )
        results["1_chat"] = "PASS: " + (r.choices[0].message.content or "")[:60]
    except Exception as exc:
        results["1_chat"] = f"FAIL: {type(exc).__name__}: {exc}"[:300]

    # 2. tool-calls + thinking, gửi lại reasoning_content
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Lấy thời tiết của một thành phố",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]
    try:
        msgs = [{"role": "user", "content": "Thời tiết Đà Lạt hôm nay thế nào?"}]
        r1 = client.chat.completions.create(
            model=model,
            messages=msgs,
            tools=tools,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        m1 = r1.choices[0].message
        if not m1.tool_calls:
            results["2_tools_thinking"] = "FAIL: mô hình không gọi công cụ"
        else:
            call = m1.tool_calls[0]
            # Gửi lại nguyên message của assistant, gồm reasoning_content
            msgs.append(m1.model_dump(exclude_none=True))
            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps({"city": "Đà Lạt", "temp_c": 19, "sky": "nhiều mây"}),
                }
            )
            r2 = client.chat.completions.create(
                model=model,
                messages=msgs,
                tools=tools,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}},
            )
            results["2_tools_thinking"] = "PASS: " + (r2.choices[0].message.content or "")[:80]
    except Exception as exc:
        results["2_tools_thinking"] = f"FAIL: {type(exc).__name__}: {exc}"[:300]

    # 3. ảnh
    try:
        b64 = base64.b64encode(tiny_png()).decode()
        r = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Ảnh này có màu chủ đạo gì? Trả lời ngắn."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }
            ],
            extra_body={"thinking": {"type": "disabled"}},
        )
        results["3_image"] = "PASS: " + (r.choices[0].message.content or "")[:80]
    except Exception as exc:
        results["3_image"] = f"FAIL: {type(exc).__name__}: {exc}"[:300]

    for name, value in results.items():
        print(f"{name}: {value}")
    return 0 if all(v.startswith("PASS") for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
