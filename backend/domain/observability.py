"""观测来源和执行身份不依赖 SDK 或持久化实现。"""

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TraceOrigin:
    schema_version: int
    trace_id: str
    span_id: str
    sampled: bool

    @classmethod
    def from_json(cls, value: Any) -> "TraceOrigin | None":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "trace_id",
            "span_id",
            "sampled",
        }:
            return None
        trace_id, span_id = value["trace_id"], value["span_id"]
        if (
            type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or type(value["sampled"]) is not bool
            or not isinstance(trace_id, str)
            or not isinstance(span_id, str)
            or re.fullmatch(r"[0-9a-f]{32}", trace_id) is None
            or re.fullmatch(r"[0-9a-f]{16}", span_id) is None
            or int(trace_id, 16) == 0
            or int(span_id, 16) == 0
        ):
            return None
        return cls(1, trace_id, span_id, value["sampled"])

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExecutionIdentity:
    task_id: str
    task_kind: str
    worker_id: str
    generation: int
    attempt: int


@dataclass(frozen=True, slots=True)
class CommitReceipt:
    identity: ExecutionIdentity
    result: str
    retry_scheduled: bool = False
    error_code: str | None = None
