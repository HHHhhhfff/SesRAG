"""本轮导出契约漂移、严格事件联合与安全边界。"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.tools.export_rag_contracts import SCHEMAS, export


def test_all_exported_rag_contracts_are_current_and_valid():
    export(check=True)
    for name in SCHEMAS:
        schema = json.loads((Path("contracts") / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)


def test_event_schema_accepts_explicit_generation_and_rejects_extra_capability_url():
    schema = json.loads(Path("contracts/run_event_v3.json").read_text(encoding="utf-8"))
    event = {
        "schema_version": 3,
        "event_id": "e",
        "run_id": "r",
        "seq": 1,
        "type": "tool.started",
        "occurred_at": "2026-10-30T00:00:00Z",
        "data": {
            "task_id": "task",
            "generation": 1,
            "attempt": 1,
            "call_id": "call",
            "execution_id": "execution",
            "stage": "retrieving",
        },
    }
    validator = Draft202012Validator(schema)
    validator.validate(event)
    with pytest.raises(ValidationError):
        validator.validate({**event, "data": {**event["data"], "url": "https://private.invalid"}})
    with pytest.raises(ValidationError):
        validator.validate({**event, "schema_version": 2})
