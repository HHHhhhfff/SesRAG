"""规范化原请求幂等摘要；不保存正文副本。"""

import hashlib
import json
from uuid import uuid4

from sqlalchemy import select

from backend.application.errors import ApplicationError
from backend.db.models import SessionOperationModel


def request_hash(kind: str, payload: dict, optional_fields=()) -> str:
    normalized = {
        "kind": kind,
        "request": payload,
        "omitted": sorted(set(optional_fields) - payload.keys()),
    }
    return hashlib.sha256(
        json.dumps(
            normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


async def replay_operation(session, thread_id, key, digest):
    if not key or len(key) > 200 or not key.strip():
        raise ApplicationError("IDEMPOTENCY_KEY_REQUIRED", "必须提供有效幂等键", 422)
    operation = await session.scalar(
        select(SessionOperationModel).where(
            SessionOperationModel.thread_id == thread_id,
            SessionOperationModel.idempotency_key == key,
        )
    )
    if operation and operation.request_hash != digest:
        raise ApplicationError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他请求", 409)
    return operation


def record_operation(
    session,
    thread_id,
    key,
    kind,
    digest,
    *,
    branch_id=None,
    message_id=None,
    run_id=None,
    task_id=None,
):
    operation = SessionOperationModel(
        operation_id=str(uuid4()),
        thread_id=thread_id,
        idempotency_key=key,
        kind=kind,
        request_hash=digest,
        result_branch_id=branch_id,
        result_message_id=message_id,
        result_run_id=run_id,
        result_task_id=task_id,
    )
    session.add(operation)
    return operation
