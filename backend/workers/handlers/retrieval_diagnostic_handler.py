"""独立诊断不造Run／Message，只执行冻结检索能力。"""

import hashlib
from functools import partial

from backend.application.errors import PermanentTaskError
from backend.application.rag_task_execution import lock_rag_execution
from backend.application.retrieval import execute_retrieval, persist_bundles
from backend.application.retrieval_views import load_scope
from backend.application.task_execution import check_locked_times, guarded_call
from backend.db.rag_models import RetrievalExecutionModel
from backend.infrastructure.rag.artifact_store import ArtifactStore


async def process_diagnostic_task(factory, settings, task_id, worker, generation):
    async with factory() as session:
        task = await lock_rag_execution(session, task_id, worker, generation)
        execution = await session.get(RetrievalExecutionModel, task.retrieval_execution_id)
        scope = await load_scope(session, settings, execution.view_id)
        snapshot, query_key, query_hash = (
            execution.snapshot_json,
            execution.private_query_key,
            execution.query_hash,
        )
    raw = ArtifactStore(settings.rag_artifact_dir).read(query_key, limit=8192)
    if hashlib.sha256(raw).hexdigest() != query_hash:
        raise PermanentTaskError("DIAGNOSTIC_INPUT_INVALID", "诊断输入身份不符")
    result = await execute_retrieval(
        factory,
        settings,
        scope,
        snapshot,
        raw.decode(),
        partial(guarded_call, factory, task_id, worker, generation),
    )
    async with factory() as session:
        task = await lock_rag_execution(session, task_id, worker, generation)
        execution = await session.get(RetrievalExecutionModel, task.retrieval_execution_id)
        lease, deadline = task.lease_expires_at, task.deadline_at
        await persist_bundles(session, execution, result)
        task.state, task.lease_expires_at = "succeeded", None
        await session.flush()
        check_locked_times(lease, deadline)
        await session.commit()
