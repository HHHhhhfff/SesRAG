from backend.application.observation import observe_control
from backend.db.models import TaskModel
from backend.domain.observability import TraceOrigin
from backend.domain.ports import TaskLease
from backend.infrastructure.queue import postgres_queue as queue


class PostgresQueue:
    """绑定应用事务的队列适配器；领域接口不接收 Session 或 ORM。"""

    def __init__(self, session, settings):
        self.session, self.settings = session, settings

    @observe_control("reclaim")
    async def reclaim(self):
        return await queue.requeue_expired(self.session)

    @observe_control("claim")
    async def claim(self, worker_id):
        task = await queue.claim_next_task(self.session, worker_id, self.settings)
        if task is None:
            return None
        return TaskLease(
            task.task_id,
            task.kind,
            task.run_id,
            task.document_id,
            worker_id,
            task.generation,
            task.attempt,
            task.index_batch_id,
            task.retrieval_execution_id,
            TraceOrigin.from_json(task.trace_origin_json),
            "missing"
            if task.trace_origin_json is None
            else "present"
            if TraceOrigin.from_json(task.trace_origin_json)
            else "invalid",
        )

    async def start(self, task):
        return await queue.mark_running(self.session, task.task_id, task.worker_id, task.generation)

    @observe_control("renew")
    async def renew(self, task):
        return await queue.renew_lease(
            self.session, task.task_id, task.worker_id, task.generation, self.settings
        )

    @observe_control("release")
    async def release(self, task):
        return await queue.release_task(
            self.session, task.task_id, task.worker_id, task.generation, self.settings
        )

    async def fail(self, task, code, *, permanent):
        accepted = await queue.schedule_retry(
            self.session,
            task.task_id,
            task.worker_id,
            task.generation,
            self.settings,
            code,
            permanent=permanent,
        )
        current = await self.session.get(TaskModel, task.task_id)
        own = (
            current is not None
            and current.worker_id == task.worker_id
            and current.generation == task.generation
        )
        return (
            "retry"
            if own and current.state == "retry_waiting"
            else "failure"
            if accepted or (own and current.state == "failed")
            else "reject"
        )
