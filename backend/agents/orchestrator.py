"""Vòng lặp agent: LLM chọn công cụ, code thực thi, kết quả quay lại LLM, sự kiện phát ra theo SSE."""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterator

from app import catalog, memory
from app.db import Database
from app.llm import ChatClient, LLMError, ReasoningDelta, TextDelta, TurnEnd, estimate_cost
from app.seed import now_ict
from .tools import TOOL_SPECS, TOOLS_BY_NAME, ToolContext, run_tool
from .prompts import DEEP_NOTE, SYSTEM_PROMPT

log = logging.getLogger("momo.agent")

MAX_HISTORY_MESSAGES = 20
MAX_TOOL_CALLS_PER_STEP = 4
THINKING_KEEPALIVE_S = 10.0
MAX_SESSIONS = 500
REF_PATTERN = re.compile(r"\b(?:evt|trp|lod|tur)_[a-z0-9_]+\b")
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]




@dataclass
class Session:
    history: list[dict] = field(default_factory=list)
    seen_refs: set[str] = field(default_factory=set)
    display: list[dict] = field(default_factory=list)  # tin nhắn hiển thị cho giao diện, dùng để khôi phục
    last_used: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionStore:
    def __init__(self, ttl_s: int = 7200, cap: int = MAX_SESSIONS, loader=None):
        self._items: dict[tuple[str, str], Session] = {}
        self._ttl, self._cap = ttl_s, cap
        self._loader = loader  # (username, sid) -> dict | None, nạp lại từ DB khi phiên không còn trong bộ nhớ
        self._lock = threading.Lock()

    def get(self, username: str, sid: str) -> Session:
        now = time.time()
        with self._lock:
            for k in [k for k, s in self._items.items() if now - s.last_used > self._ttl]:
                del self._items[k]
            if len(self._items) >= self._cap and (username, sid) not in self._items:
                oldest = min(self._items, key=lambda k: self._items[k].last_used)
                del self._items[oldest]
            sess = self._items.get((username, sid))
            if sess is None:
                sess = Session()
                saved = self._loader(username, sid) if self._loader else None
                if saved:
                    sess.history, sess.seen_refs, sess.display = saved["history"], saved["seen_refs"], saved["display"]
                self._items[(username, sid)] = sess
            sess.last_used = now
            return sess


def build_system_prompt(db: Database, username: str, mode: str, now: datetime | None = None) -> str:
    now = now or now_ict()
    mem = memory.recall(db, username)
    mem_text = "; ".join(f"{memory.ALLOWED_KEYS[k]}={v}" for k, v in mem.items()) or "(chưa có)"
    return SYSTEM_PROMPT.format(weekday=WEEKDAYS[now.weekday()], today=now.strftime("%d/%m/%Y"), memory=mem_text,
                                mode_note=DEEP_NOTE if mode == "deep" else "")


@dataclass
class AgentDeps:
    db: Database
    llm: ChatClient
    max_steps: int = 6
    # Gọi sau mỗi lượt LLM hoàn tất (prompt_tokens, completion_tokens). Dùng để ghi chi phí ngay,
    # kể cả khi người dùng ngắt kết nối giữa chừng và sự kiện "done" không bao giờ được gửi.
    on_usage: Callable[[int, int], None] | None = None


SHOWN_PREFIX = "[Mục đã hiển thị cho người dùng, theo thứ tự trên màn hình: "


def _shown_note(ctx: ToolContext, shown: dict[str, str]) -> str:
    if not shown:
        return ""
    items = "; ".join(f"{n}) {rid} = {label}" for n, (rid, label) in enumerate(list(shown.items())[:12], start=1))
    return f"\n{SHOWN_PREFIX}{items}]"


def run_turn(deps: AgentDeps, session: Session, username: str, text: str, mode: str = "fast",
             image_url: str | None = None) -> Iterator[dict]:
    mode = "deep" if mode == "deep" else "fast"
    ctx = ToolContext(db=deps.db, username=username, seen_refs=session.seen_refs)
    for rid in REF_PATTERN.findall(text):  # người dùng tự nêu mã (ví dụ bấm nút Chọn trên thẻ)
        if catalog.get_item(deps.db, rid):
            session.seen_refs.add(rid)

    user_content: str | list = text
    if image_url:
        user_content = [{"type": "text", "text": text or "Hãy xem ảnh này và gợi ý giúp mình."},
                        {"type": "image_url", "image_url": {"url": image_url}}]
    messages = [{"role": "system", "content": build_system_prompt(deps.db, username, mode)},
                *session.history, {"role": "user", "content": user_content}]

    texts: list[str] = []
    shown: dict[str, str] = {}
    prompt_tokens = completion_tokens = 0
    failed = False
    last_thinking_event = float("-inf")
    finished = False

    for _ in range(deps.max_steps):
        turn = None
        step_started_text = False
        try:
            for ev in deps.llm.stream(messages, TOOL_SPECS, mode):
                if isinstance(ev, TextDelta):
                    if not step_started_text and texts:  # tách đoạn dẫn trước và sau khi gọi công cụ
                        texts.append("\n\n")
                        yield {"type": "text_delta", "text": "\n\n"}
                    step_started_text = True
                    texts.append(ev.text)
                    yield {"type": "text_delta", "text": ev.text}
                elif isinstance(ev, ReasoningDelta):
                    # Phát lại định kỳ để kết nối không bị proxy ngắt vì im lặng khi mô hình nghĩ lâu.
                    if time.monotonic() - last_thinking_event > THINKING_KEEPALIVE_S:
                        last_thinking_event = time.monotonic()
                        yield {"type": "thinking"}
                elif isinstance(ev, TurnEnd):
                    turn = ev.turn
        except LLMError as exc:
            log.warning("LLM error: %s", exc)
            failed = True
            yield {"type": "error", "message": "Dịch vụ AI tạm thời gặp lỗi, bạn thử lại sau ít phút nhé."}
            break
        if turn is None:
            failed = True
            yield {"type": "error", "message": "Dịch vụ AI không trả lời, bạn thử lại nhé."}
            break
        prompt_tokens += turn.prompt_tokens
        completion_tokens += turn.completion_tokens
        if deps.on_usage:
            deps.on_usage(turn.prompt_tokens, turn.completion_tokens)
        if not turn.tool_calls:
            finished = True
            break
        messages.append(turn.to_message(keep_reasoning=(mode == "deep")))
        for i, tc in enumerate(turn.tool_calls):
            tool = TOOLS_BY_NAME.get(tc.name)
            label = tool.label if tool else tc.name
            if i >= MAX_TOOL_CALLS_PER_STEP:
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": '{"error": "Quá nhiều lệnh gọi công cụ trong một bước"}'})
                continue
            yield {"type": "tool_status", "tool": tc.name, "status": "running", "label": label}
            content, block, is_error = run_tool(ctx, tc.name, tc.arguments)
            yield {"type": "tool_status", "tool": tc.name, "status": "error" if is_error else "done"}
            if block:
                yield {"type": "ui_block", "block": block}
                for it in block.get("items", []):
                    shown[it["ref_id"]] = f"{it['title']}, {it['price_vnd']}đ/{it.get('price_unit', '')}"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})

    if not failed and not finished:
        note = "Mình chưa hoàn tất được yêu cầu trong số bước cho phép. Bạn thử chia nhỏ yêu cầu nhé."
        texts.append(note)
        yield {"type": "text_delta", "text": note}

    if not failed:
        session.history.append({"role": "user", "content": (text + " [kèm 1 ảnh]") if image_url else text})
        session.history.append({"role": "assistant", "content": "".join(texts) + _shown_note(ctx, shown)})
        del session.history[:-MAX_HISTORY_MESSAGES]
    yield {"type": "done", "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                                     "cost_usd": round(estimate_cost(prompt_tokens, completion_tokens), 6)}}
