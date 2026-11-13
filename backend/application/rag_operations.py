"""资源操作幂等；不把文件hash误认为远端幂等保证。"""

import hashlib
from uuid import uuid4

from sqlalchemy import select, text

from backend.application.errors import ApplicationError
from backend.db.rag_models import RagOperationModel


async def transaction_lock(session, name):
    if session.bind.dialect.name == "postgresql":
        identity = int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big", signed=True)
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:identity)"), {"identity": identity}
        )


async def replay(session, owner, scope, key, request_hash):
    if not isinstance(key, str) or not 1 <= len(key) <= 200:
        raise ApplicationError("IDEMPOTENCY_KEY_REQUIRED", "需要有效的 Idempotency-Key", 422)
    # 不存在的记录不能被FOR UPDATE锁住；相同逻辑键先用事务锁串行化首次创建。
    await transaction_lock(session, f"rag-operation:{owner}:{scope}:{key}")
    row = await session.scalar(
        select(RagOperationModel)
        .where(
            RagOperationModel.owner_id == owner,
            RagOperationModel.scope == scope,
            RagOperationModel.idempotency_key == key,
        )
        .with_for_update()
    )
    if row and row.request_hash != request_hash:
        raise ApplicationError("IDEMPOTENCY_CONFLICT", "同一操作键不能改变内容", 409)
    return row.result_json if row else None


def record(session, owner, scope, key, hashed, result):
    session.add(
        RagOperationModel(
            operation_id=str(uuid4()),
            owner_id=owner,
            scope=scope,
            idempotency_key=key,
            request_hash=hashed,
            result_json=result,
            storage_reservation_json=session.info.pop("rag_reservation", {}),
        )
    )
