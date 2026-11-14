"""只接受已知字段和固定消息；不尝试清洗任意正文或异常字符串。"""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

ACTIONS = {
    "request": "请求处理结束",
    "claim": "任务已领取",
    "renew": "任务已续租",
    "reclaim": "过期任务回收",
    "release": "停机释放任务",
    "stage": "执行阶段结束",
    "attempt": "执行尝试结束",
    "enqueue": "任务入队事务结束",
    "diagnostic": "观测组件降级",
    "startup": "应用观测已启动",
    "shutdown": "应用观测已关闭",
    "reject": "执行授权已拒绝",
    "failure": "任务控制失败",
    "retry": "任务已安排重试",
    "success": "执行函数返回",
}
ACTIONS.update(
    {
        "attempt_" + result: message
        for result, message in {
            "succeeded": "执行尝试已提交成功",
            "failed": "执行尝试已提交失败",
            "yielded": "执行尝试已正常让出",
            "cancelled": "执行尝试已确认取消",
            "lease_lost": "执行尝试失去租约",
            "released": "执行尝试已停机释放",
            "unknown": "执行尝试结果未获提交确认",
        }.items()
    }
)
ID_FIELDS = (
    "thread_id",
    "run_id",
    "task_id",
    "worker_id",
    "document_id",
    "index_batch_id",
    "parse_job_id",
    "retrieval_execution_id",
)
STAGES = {
    "parse",
    "chunk",
    "embed",
    "retrieval",
    "query_embedding",
    "dense_search",
    "rerank",
    "enhancement",
    "context",
    "generation",
    "publish",
    "run",
    "index_document",
    "index_build",
    "retrieval_diagnostic",
}
ERROR_CODES = frozenset(
    json.loads(
        (
            Path(__file__).resolve().parents[3] / "contracts/observability/error_codes_v1.json"
        ).read_text(encoding="utf-8")
    )
)


def safe_error(value):
    return None if value is None else value if value in ERROR_CODES else "UNKNOWN_ERROR"


def encode_record(service, environment, action, fields):
    action = action if action in ACTIONS else "diagnostic"
    data = dict(
        schema_version=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        level="INFO",
        service=service,
        environment=environment,
        action=action,
        message=ACTIONS[action],
        trace_id=None,
        span_id=None,
        trace_sampled=None,
        origin_state="disabled",
    )
    for key, size in (("trace_id", 32), ("span_id", 16)):
        value = fields.get(key)
        if isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{size}}}", value) and int(value, 16):
            data[key] = value
    if data["trace_id"] and data["span_id"] and type(fields.get("trace_sampled")) is bool:
        data["trace_sampled"] = fields["trace_sampled"]
    if fields.get("origin_state") in {"present", "missing", "invalid", "disabled"}:
        data["origin_state"] = fields["origin_state"]
    for key in ID_FIELDS:
        value = fields.get(key)
        data[key] = (
            value
            if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value)
            else None
        )
    for key in ("generation", "attempt"):
        value = fields.get(key)
        data[key] = value if type(value) is int and 0 <= value <= 2**53 else None
    value = fields.get("duration_ms")
    data["duration_ms"] = (
        min(value, 86400000)
        if isinstance(value, (float, int)) and math.isfinite(value) and value >= 0
        else None
    )
    data["stage"] = fields.get("stage") if fields.get("stage") in STAGES else None
    data["error_code"] = safe_error(fields.get("error_code"))
    line = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(line.encode()) > 4096:
        raise ValueError("safe log exceeds budget")
    return line
