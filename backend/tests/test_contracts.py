import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SCHEMAS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (CONTRACTS / "schemas").glob("*.json")}
REGISTRY = Registry().with_resources(
    (name, Resource.from_contents(schema, default_specification=DRAFT202012))
    for name, schema in SCHEMAS.items()
)


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(SCHEMAS[name], registry=REGISTRY)


def test_every_schema_is_valid():
    for name, schema in SCHEMAS.items():
        Draft202012Validator.check_schema(schema)


def test_every_schema_has_examples():
    examples = {p.stem for p in (CONTRACTS / "examples").glob("*.json")}
    assert examples == set(SCHEMAS)


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_examples_match_schema(name):
    instances = json.loads((CONTRACTS / "examples" / f"{name}.json").read_text(encoding="utf-8"))
    assert instances, "file mẫu rỗng"
    v = validator(name)
    for inst in instances:
        errors = list(v.iter_errors(inst))
        assert not errors, errors[0].message


def test_invalid_instance_is_rejected():
    bad = {"id": "x", "kind": "movie"}
    assert list(validator("event").iter_errors(bad))
    assert list(validator("order_draft").iter_errors({"id": "ord_1", "status": "paid", "items": [], "total_vnd": 0, "created_at": "2026-01-01T00:00:00+07:00"}))
