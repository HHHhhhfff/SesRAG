"""版本化字典是应用和005共用的真源。"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from prometheus_client import generate_latest

from backend.infrastructure.observability.metrics import ObservabilityMetrics


def test_catalog_matches_runtime_and_has_bounded_series():
    root = Path("contracts/observability")
    schema = json.loads((root / "capabilities_v1.json").read_text(encoding="utf-8"))
    catalog = json.loads((root / "metrics_v1.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema["$defs"]["metrics_catalog"]).validate(catalog)
    for role in ("api", "worker"):
        metrics = ObservabilityMetrics(f"sesrag-{role}", "local")
        output = generate_latest(metrics.registry).decode()
        assert "_created" not in output
        assert len([line for line in output.splitlines() if not line.startswith("#")]) <= 12000
        assert set(metrics.catalog_names) == {
            item["name"] for item in catalog if role in item["roles"]
        }


@pytest.mark.parametrize(
    "mutation", ["missing_protocol", "extra_field", "wrong_topology", "public_target"]
)
def test_capability_nested_contract_rejects_missing_or_unexpected_fields(mutation):
    root = Path("contracts/observability")
    schema = json.loads((root / "capabilities_v1.json").read_text(encoding="utf-8"))
    value = json.loads((root / "application_v1.example.json").read_text(encoding="utf-8"))
    if mutation == "missing_protocol":
        del value["tracing"]["protocol"]
    if mutation == "extra_field":
        value["logging"]["raw_prompt"] = True
    if mutation == "wrong_topology":
        value["tracing"]["topology"] = "long_lived_run"
    if mutation == "public_target":
        value["services"]["api"]["targets"][0]["host"] = "https://public/path"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(value)
