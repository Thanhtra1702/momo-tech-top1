"""Lớp gọi LLM không phụ thuộc nhà cung cấp (API tương thích OpenAI, mặc định DeepSeek).

Hai chế độ:
  fast: thinking tắt, trả lời nhanh, rẻ.
  deep: thinking bật (reasoning_effort=high), dùng cho yêu cầu nhiều ràng buộc.

Khi thinking bật kèm tool-calls, reasoning_content của lượt assistant phải được gửi lại ở các lượt sau
trong cùng một vòng gọi công cụ. Agent giữ nguyên trường này trong message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Protocol

from ..config import Settings

FAST_MAX_TOKENS = 2048
DEEP_MAX_TOKENS = 8192

# USD cho 1 triệu token. Lấy giá cao điểm, không tính cache hit, nên ước tính hơi cao (an toàn cho trần chi phí).
PRICE_IN_PER_M = 0.30
PRICE_OUT_PER_M = 1.20


class ConfigError(RuntimeError):
    """Thiếu hoặc sai cấu hình, ví dụ chưa đặt LLM_API_KEY."""


class LLMError(RuntimeError):
    """Lỗi khi gọi nhà cung cấp LLM (mạng, hạn mức, timeout...)."""


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * PRICE_IN_PER_M + completion_tokens * PRICE_OUT_PER_M) / 1_000_000


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # chuỗi JSON thô từ mô hình


@dataclass
class AssistantTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def to_message(self, keep_reasoning: bool) -> dict:
        msg: dict[str, Any] = {"role": "assistant", "content": self.text or None}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": t.id, "type": "function", "function": {"name": t.name, "arguments": t.arguments}}
                for t in self.tool_calls
            ]
        if keep_reasoning and self.reasoning:
            msg["reasoning_content"] = self.reasoning
        return msg


@dataclass
class TextDelta:
    text: str


@dataclass
class ReasoningDelta:
    text: str


@dataclass
class TurnEnd:
    turn: AssistantTurn


LLMEvent = TextDelta | ReasoningDelta | TurnEnd


class ChatClient(Protocol):
    def stream(self, messages: list[dict], tools: list[dict] | None = None, mode: str = "fast") -> Iterator[LLMEvent]: ...


def request_options(mode: str) -> dict:
    if mode == "deep":
        return {"max_tokens": DEEP_MAX_TOKENS,
                "extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}}
    return {"max_tokens": FAST_MAX_TOKENS, "extra_body": {"thinking": {"type": "disabled"}}}


class LLMClient:
    def __init__(self, settings: Settings):
        if not settings.llm_api_key:
            raise ConfigError("Thiếu LLM_API_KEY. Đặt biến môi trường LLM_API_KEY (xem .env.example).")
        from openai import OpenAI  # import muộn để test không cần SDK

        self._settings = settings
        self._client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url,
                              timeout=settings.llm_timeout_s, max_retries=1)

    def stream(self, messages: list[dict], tools: list[dict] | None = None, mode: str = "fast") -> Iterator[LLMEvent]:
        kwargs: dict[str, Any] = dict(model=self._settings.llm_model, messages=messages, stream=True,
                                      stream_options={"include_usage": True}, **request_options(mode))
        if tools:
            kwargs["tools"] = tools
        try:
            response = self._client.chat.completions.create(**kwargs)
            text, reasoning = [], []
            calls: dict[int, ToolCall] = {}
            usage = (0, 0)
            for chunk in response:
                if getattr(chunk, "usage", None):
                    usage = (chunk.usage.prompt_tokens or 0, chunk.usage.completion_tokens or 0)
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                rc = getattr(delta, "reasoning_content", None) or (getattr(delta, "model_extra", None) or {}).get("reasoning_content")
                if rc:
                    reasoning.append(rc)
                    yield ReasoningDelta(rc)
                if delta.content:
                    text.append(delta.content)
                    yield TextDelta(delta.content)
                for tc in delta.tool_calls or []:
                    cur = calls.setdefault(tc.index, ToolCall(id="", name="", arguments=""))
                    if tc.id:
                        cur.id = tc.id
                    if tc.function and tc.function.name:
                        cur.name += tc.function.name
                    if tc.function and tc.function.arguments:
                        cur.arguments += tc.function.arguments
        except LLMError:
            raise
        except Exception as exc:  # SDK ném nhiều loại lỗi khác nhau; không đưa chi tiết ra ngoài
            raise LLMError(f"Gọi LLM thất bại: {type(exc).__name__}") from exc
        yield TurnEnd(AssistantTurn(
            text="".join(text), tool_calls=[calls[i] for i in sorted(calls)], reasoning="".join(reasoning),
            prompt_tokens=usage[0], completion_tokens=usage[1],
        ))


Script = AssistantTurn | Callable[[list[dict]], AssistantTurn]


class FakeLLMClient:
    """Bản giả cho test: phát lần lượt các lượt đã kịch bản hóa."""

    def __init__(self, script: list[Script] | None = None, reply: str | None = None):
        self._script = list(script or [])
        self._reply = reply
        self.calls: list[dict] = []

    def stream(self, messages: list[dict], tools: list[dict] | None = None, mode: str = "fast") -> Iterator[LLMEvent]:
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools, "mode": mode})
        if self._script:
            step = self._script.pop(0)
            turn = step(messages) if callable(step) else step
        else:
            last = messages[-1].get("content") if messages else ""
            turn = AssistantTurn(text=self._reply if self._reply is not None else f"echo: {last}")
        if turn.reasoning:
            yield ReasoningDelta(turn.reasoning)
        if turn.text:
            mid = max(1, len(turn.text) // 2)
            yield TextDelta(turn.text[:mid])
            if turn.text[mid:]:
                yield TextDelta(turn.text[mid:])
        yield TurnEnd(turn)
