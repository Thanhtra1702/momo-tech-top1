import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from app.llm import AssistantTurn, ToolCall

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SCHEMAS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (CONTRACTS / "schemas").glob("*.json")}
REGISTRY = Registry().with_resources(
    (name, Resource.from_contents(s, default_specification=DRAFT202012)) for name, s in SCHEMAS.items()
)


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(SCHEMAS[name], registry=REGISTRY)


def call(name: str, args: dict, cid: str = "c1") -> ToolCall:
    return ToolCall(id=cid, name=name, arguments=json.dumps(args, ensure_ascii=False))


def tool_turn(*calls: ToolCall, text: str = "", reasoning: str = "") -> AssistantTurn:
    return AssistantTurn(text=text, tool_calls=list(calls), reasoning=reasoning, prompt_tokens=100, completion_tokens=20)


def text_turn(text: str) -> AssistantTurn:
    return AssistantTurn(text=text, prompt_tokens=100, completion_tokens=30)


def parse_sse(body: str) -> list[dict]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
