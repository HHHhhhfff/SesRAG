"""Task 来源只接受有限、真实的追踪身份。"""

import pytest

from backend.domain.observability import TraceOrigin


def test_trace_origin_roundtrip():
    value = {"schema_version": 1, "trace_id": "1" * 32, "span_id": "2" * 16, "sampled": True}
    assert TraceOrigin.from_json(value).to_json() == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        {"schema_version": 2, "trace_id": "1" * 32, "span_id": "2" * 16, "sampled": True},
        {"schema_version": 1, "trace_id": "0" * 32, "span_id": "2" * 16, "sampled": True},
        {"schema_version": 1, "trace_id": "1" * 32, "span_id": "2" * 16, "sampled": 1},
        {
            "schema_version": 1,
            "trace_id": "1" * 32,
            "span_id": "2" * 16,
            "sampled": True,
            "baggage": "secret",
        },
    ],
)
def test_invalid_or_untrusted_origin_is_missing(value):
    assert TraceOrigin.from_json(value) is None
