from types import SimpleNamespace as NS

import pytest

from app.config import Settings
from app.llm import (AssistantTurn, ConfigError, LLMClient, LLMError, ReasoningDelta, TextDelta, ToolCall, TurnEnd,
                     estimate_cost, request_options)


def chunk(content=None, reasoning=None, tool_calls=None, usage=None, choices=True):
    delta = NS(content=content, reasoning_content=reasoning, tool_calls=tool_calls, model_extra={})
    return NS(choices=[NS(delta=delta)] if choices else [], usage=usage)


def tc(index, id=None, name=None, args=None):
    return NS(index=index, id=id, function=NS(name=name, arguments=args))


class StubCompletions:
    def __init__(self, chunks=None, exc=None):
        self.chunks, self.exc, self.kwargs = chunks or [], exc, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.exc:
            raise self.exc
        return iter(self.chunks)


def client_with(stub) -> LLMClient:
    c = LLMClient(Settings(llm_api_key="k"))
    c._client = NS(chat=NS(completions=stub))
    return c


def test_missing_key_raises_config_error():
    with pytest.raises(ConfigError, match="LLM_API_KEY"):
        LLMClient(Settings(llm_api_key=""))


def test_request_options_per_mode():
    fast, deep = request_options("fast"), request_options("deep")
    assert fast["extra_body"] == {"thinking": {"type": "disabled"}}
    assert deep["extra_body"] == {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}
    assert deep["max_tokens"] > fast["max_tokens"]


def test_streams_text_reasoning_and_tool_calls():
    stub = StubCompletions([
        chunk(reasoning="nghĩ "), chunk(reasoning="tiếp"),
        chunk(content="Xin "), chunk(content="chào"),
        chunk(tool_calls=[tc(0, id="call_1", name="search_", args='{"ci')]),
        chunk(tool_calls=[tc(0, name="events", args='ty": "Huế"}')]),
        chunk(tool_calls=[tc(1, id="call_2", name="get_places", args="{}")]),
        chunk(choices=False, usage=NS(prompt_tokens=120, completion_tokens=45)),
    ])
    events = list(client_with(stub).stream([{"role": "user", "content": "hi"}], [{"type": "function"}], mode="deep"))
    assert [type(e) for e in events[:4]] == [ReasoningDelta, ReasoningDelta, TextDelta, TextDelta]
    turn = events[-1].turn
    assert isinstance(events[-1], TurnEnd)
    assert turn.text == "Xin chào" and turn.reasoning == "nghĩ tiếp"
    assert turn.tool_calls == [ToolCall("call_1", "search_events", '{"city": "Huế"}'), ToolCall("call_2", "get_places", "{}")]
    assert (turn.prompt_tokens, turn.completion_tokens) == (120, 45)
    kw = stub.kwargs
    assert kw["stream"] is True and kw["tools"] == [{"type": "function"}]
    assert kw["extra_body"]["thinking"] == {"type": "enabled"} and kw["model"] == "deepseek-flash"


def test_provider_errors_are_wrapped_without_leaking_details():
    c = client_with(StubCompletions(exc=RuntimeError("Bearer sk-secret-123 rejected")))
    with pytest.raises(LLMError) as e:
        list(c.stream([{"role": "user", "content": "hi"}]))
    assert "sk-secret" not in str(e.value)


def test_assistant_turn_message_format():
    t = AssistantTurn(text="", tool_calls=[ToolCall("c1", "get_places", "{}")], reasoning="r")
    assert t.to_message(True)["reasoning_content"] == "r"
    assert "reasoning_content" not in t.to_message(False)
    assert t.to_message(True)["content"] is None
    assert t.to_message(True)["tool_calls"][0]["function"] == {"name": "get_places", "arguments": "{}"}


def test_cost_estimate_is_positive_and_monotonic():
    assert estimate_cost(0, 0) == 0
    assert estimate_cost(1_000_000, 0) == pytest.approx(0.30)
    assert estimate_cost(1000, 1000) < estimate_cost(2000, 1000)


def test_load_dotenv_reads_file_without_overriding(tmp_path, monkeypatch):
    from app.config import load_dotenv

    env = tmp_path / ".env"
    env.write_text('# ghi chú\nLLM_API_KEY="abc123"\nLLM_MODEL=deepseek-flash\nEMPTY=\nKEEP=from_file\n', encoding="utf-8")
    for k in ("LLM_API_KEY", "LLM_MODEL", "EMPTY", "KEEP"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("KEEP", "from_shell")
    assert load_dotenv([env]) == [env]
    import os
    assert os.environ["LLM_API_KEY"] == "abc123" and os.environ["LLM_MODEL"] == "deepseek-flash"
    assert os.environ["KEEP"] == "from_shell"
    monkeypatch.delenv("LLM_API_KEY"); monkeypatch.delenv("LLM_MODEL"); monkeypatch.delenv("EMPTY", raising=False)
    assert load_dotenv([tmp_path / "missing.env"]) == []
