"""真实应用/队列/Journal 事务，外部模型使用受控流。"""

import asyncio
from datetime import timedelta, timezone

import pytest
from sqlalchemy import func, select

from backend.api.schemas.v2.runs import EventResponse, RunOperationCreate
from backend.api.schemas.v2.threads import MessageCreate
from backend.application.errors import TransientTaskError
from backend.application.session_runs import (
    cancel_session_run,
    context_detail,
    create_related_run,
    create_session_message,
)
from backend.application.task_execution import ExecutionStopped, complete_run
from backend.application.threads import create_thread
from backend.db.models import (
    BranchModel,
    ContextPlanModel,
    MessageModel,
    ModelProfileModel,
    RunModel,
    TaskModel,
)
from backend.domain.ports import Evidence
from backend.infrastructure.events.journal import list_events
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.queue import postgres_queue as queue
from backend.workers.runtime import WorkerRuntime
from tests.integration.test_provider_http import provider_server as provider_server


@pytest.fixture
async def workspace(document_db):
    settings, factory = document_db
    async with factory() as session:
        session.add(
            ModelProfileModel(
                profile_id="mock-default",
                version=1,
                display_name="Mock",
                provider_kind="mock",
                model_name="mock",
                generation_params={},
                context_window_tokens=8192,
                max_output_tokens=1024,
                status="enabled",
                is_default=True,
                tokenizer_kind="mock",
                tokenizer_version="1",
                tokenizer_config={"safety_margin_tokens": 128, "summary_max_tokens": 512},
            )
        )
        await session.commit()
        thread = await create_thread(session, settings, "workspace", conversation_version=2)
        branch = await session.scalar(
            select(BranchModel).where(BranchModel.thread_id == thread.thread_id)
        )
    return settings, factory, thread.thread_id, branch.branch_id


async def submit(workspace, content="question", version=0, key="one", branch_id=None):
    settings, factory, tid, bid = workspace
    async with factory() as session:
        result, _ = await create_session_message(
            session,
            settings,
            tid,
            MessageCreate(branch_id=branch_id or bid, content=content, expected_version=version),
            key,
        )
        return result


class EmptyStore:
    def __init__(self, _session):
        pass

    async def search(self, *args):
        return []


def runtime(workspace, provider=None, store=EmptyStore):
    settings, factory, *_ = workspace
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings), vector_store_factory=store)
    if provider:
        worker.model_provider = provider
    return worker


async def facts(workspace, rid):
    settings, factory, *_ = workspace
    async with factory() as session:
        run = await session.get(RunModel, rid)
        task = await session.get(TaskModel, run.primary_task_id)
        events = await list_events(session, rid)
        for event in events:
            EventResponse.model_validate(
                dict(
                    schema_version=event.schema_version,
                    event_id=event.event_id,
                    run_id=rid,
                    seq=event.seq,
                    type=event.type,
                    occurred_at=event.created_at,
                    data=event.payload_json,
                )
            )
        return run, task, events


async def test_real_worker_model_request_history_isolation_selected_evidence(workspace):
    class EvidenceStore(EmptyStore):
        async def search(self, *args):
            return [
                Evidence("doc", "keep", "batch", "safe.txt", "tiny evidence", 0, 13, 1.0, ()),
                Evidence("doc", "omit", "batch", "large.txt", "x " * 40_000, 0, 80_000, 0.1, ()),
            ]

    class Provider:
        def __init__(self):
            self.requests = []

        async def stream_request(self, request):
            self.requests.append(request)
            yield "answer"

    provider = Provider()
    worker = runtime(workspace, provider, EvidenceStore)
    first = await submit(workspace, "allowed sentinel")
    assert await worker.run_once()
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == task.state == "succeeded", run.last_error_code
    assert [e.type for e in events][-2:] == ["message.completed", "run.succeeded"]
    assert all(e.schema_version == 2 for e in events)
    assert events[-1].payload_json["generation"] == 1
    assert provider.requests[0].selected_evidence == (("doc", "keep"),)
    settings, factory, tid, bid = workspace
    async with factory() as session:
        assistant = await session.get(MessageModel, run.assistant_message_id)
        assert [c["chunk_id"] for c in assistant.citations_json] == ["keep"]
        context = await context_detail(session, settings, run.run_id)
        assert [e["chunk_id"] for e in context["plan"]["selected_evidence"]] == ["keep"]
        assert "summary_text" not in str(context)
        other = await create_thread(session, settings, "private", conversation_version=2)
        other_branch = await session.scalar(
            select(BranchModel).where(BranchModel.thread_id == other.thread_id)
        )
        await create_session_message(
            session,
            settings,
            other.thread_id,
            MessageCreate(
                branch_id=other_branch.branch_id, content="forbidden sentinel", expected_version=0
            ),
            "private",
        )
        # 暂取消另一 Thread，避免它影响本测试领取顺序。
        other_run = await session.scalar(
            select(RunModel).where(RunModel.thread_id == other.thread_id)
        )
        await cancel_session_run(session, settings, other_run.run_id)
    second = await submit(workspace, "followup", 2, "two")
    assert await worker.run_once()
    run, _, _ = await facts(workspace, second["run_id"])
    assert run.status == "succeeded"
    sent = "|".join(m.content for m in provider.requests[-1].messages)
    assert "allowed sentinel" in sent and "answer" in sent
    assert "forbidden sentinel" not in sent


@pytest.mark.parametrize("state", ["queued", "retry_waiting", "leased", "running"])
async def test_cancellation_task_state_ack_and_reclaim_priority(workspace, state):
    first = await submit(workspace)
    settings, factory, *_ = workspace
    async with factory() as session:
        if state in {"leased", "running"}:
            await queue.claim_next_task(session, "w", settings)
            if state == "running":
                await queue.mark_running(session, first["task_id"], "w", 1)
        elif state == "retry_waiting":
            task = await session.get(TaskModel, first["task_id"])
            task.state = "retry_waiting"
            await session.commit()
        run = await cancel_session_run(session, settings, first["run_id"])
        assert run.status == ("cancelling" if state in queue.ACTIVE else "cancelled")
    if state in queue.ACTIVE:
        async with factory() as session:
            assert not await queue.renew_lease(session, first["task_id"], "w", 1, settings)
        async with factory() as session:
            await queue.schedule_retry(session, first["task_id"], "w", 1, settings, "LATE_FAILURE")
        run, task, events = await facts(workspace, first["run_id"])
        assert run.status == task.state == "cancelled"
        assert [e.type for e in events].count("run.cancelled") == 1
        assert not any(e.type in {"run.failed", "task.retry_scheduled"} for e in events)


async def test_worker_observes_cancel_and_acknowledges_without_requeue(workspace):
    first = await submit(workspace)
    entered = asyncio.Event()
    closed = asyncio.Event()

    class Provider:
        async def stream_request(self, request):
            try:
                yield "draft"
                entered.set()
                await asyncio.Event().wait()
            finally:
                closed.set()

    worker = runtime(workspace, Provider())
    pending = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(entered.wait(), 3)
    settings, factory, *_ = workspace
    async with factory() as session:
        assert (await cancel_session_run(session, settings, first["run_id"])).status == "cancelling"
    await asyncio.wait_for(pending, 3)
    assert closed.is_set()
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == task.state == "cancelled"
    assert run.assistant_message_id is None
    assert events[-1].type == "run.cancelled"


async def test_mandatory_budget_fails_before_embedding_and_publishes_plan(workspace):
    first = await submit(workspace, "! " * 9_000)
    worker = runtime(workspace)

    class Never:
        def embed(self, *args):
            raise AssertionError("must not embed mandatory overflow")

    worker.embedding_provider = Never()
    assert await worker.run_once()
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == task.state == "failed"
    assert run.last_error_code == "CONTEXT_TOO_LARGE"
    settings, factory, *_ = workspace
    async with factory() as session:
        detail = await context_detail(session, settings, run.run_id)
        assert detail["plan"]["status"] == "budget_exceeded"
    assert not any(e.type == "retrieval.completed" for e in events)


async def test_regenerate_distinct_children_exclude_old_answer_reuse_input(workspace):
    first = await submit(workspace)
    assert await runtime(workspace).run_once()
    settings, factory, *_ = workspace
    async with factory() as session:
        source = await session.get(RunModel, first["run_id"])
        old_events = [(e.seq, e.payload_json) for e in await list_events(session, source.run_id)]
        one, _ = await create_related_run(
            session, settings, source.run_id, RunOperationCreate(), "r1", "regenerate"
        )
        two, _ = await create_related_run(
            session, settings, source.run_id, RunOperationCreate(), "r2", "regenerate"
        )
        assert one["branch_id"] != two["branch_id"]
        assert one["message_id"] == two["message_id"] == source.user_message_id
        assert [
            (e.seq, e.payload_json) for e in await list_events(session, source.run_id)
        ] == old_events
        user = await session.get(MessageModel, source.user_message_id)
        assert user.run_id == source.run_id
        assert (
            await session.scalar(
                select(func.count()).select_from(MessageModel).where(MessageModel.role == "user")
            )
            == 1
        )


async def test_automatic_retry_keeps_run_task_input_and_attempt_plans(workspace):
    first = await submit(workspace)

    class Provider:
        def __init__(self):
            self.calls = 0

        async def stream_request(self, request):
            self.calls += 1
            yield "old draft" if self.calls == 1 else "final answer"
            if self.calls == 1:
                raise TransientTaskError("UPSTREAM_TEMPORARY", "retry")

    provider = Provider()
    worker = runtime(workspace, provider)
    assert await worker.run_once()
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == "retry_waiting"
    settings, factory, *_ = workspace
    async with factory() as session:
        saved = await session.get(TaskModel, first["task_id"])
        saved.available_at = queue.utc_now() - timedelta(seconds=1)
        await session.commit()
    assert await worker.run_once()
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == task.state == "succeeded"
    assert task.attempt == task.generation == 2
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    async with factory() as session:
        plans = (
            await session.scalars(
                select(ContextPlanModel).where(ContextPlanModel.run_id == run.run_id)
            )
        ).all()
        assert sorted(p.generation for p in plans) == [1, 2]
        answer = await session.get(MessageModel, run.assistant_message_id)
        assert answer.content == "final answer"


async def test_first_delta_flushes_while_provider_stalls(workspace):
    first = await submit(workspace)
    allow_finish = asyncio.Event()
    entered = asyncio.Event()

    class Provider:
        async def stream_request(self, request):
            yield "first"
            entered.set()
            await allow_finish.wait()
            yield "second"

    worker = runtime(workspace, Provider())
    pending = asyncio.create_task(worker.run_once())
    try:
        await asyncio.wait_for(entered.wait(), 3)

        async def delta_visible():
            while True:
                _, _, events = await facts(workspace, first["run_id"])
                if any(e.type == "answer.delta" for e in events):
                    return
                await asyncio.sleep(0.01)

        await asyncio.wait_for(delta_visible(), 0.5)
    finally:
        allow_finish.set()
        await asyncio.wait_for(pending, 3)
    run, _, _ = await facts(workspace, first["run_id"])
    assert run.status == "succeeded"


async def frozen_limits(workspace, rid, **limits):
    _, factory, *_ = workspace
    async with factory() as session:
        run = await session.get(RunModel, rid)
        snapshot = {**run.snapshot_json, "execution": {**run.snapshot_json["execution"], **limits}}
        run.snapshot_json = snapshot
        await session.commit()


@pytest.mark.parametrize(
    "limit,value,expected",
    [
        ("max_regular_events", 2, "RUN_EVENT_LIMIT"),
        ("max_regular_events", 3, "RUN_EVENT_LIMIT"),
        ("max_regular_events", 6, "RUN_EVENT_LIMIT"),
        ("max_output_chars", 3, "ANSWER_LIMIT_EXCEEDED"),
        ("max_raw_deltas", 1, "ANSWER_LIMIT_EXCEEDED"),
        ("delta_buffer_bytes", 3, "DELTA_BUFFER_LIMIT"),
    ],
)
async def test_frozen_resource_limits_fail_with_reserved_terminal(
    workspace, limit, value, expected
):
    first = await submit(workspace)
    await frozen_limits(workspace, first["run_id"], **{limit: value})

    class Provider:
        async def stream_request(self, request):
            yield "draft"
            yield "more"

    await runtime(workspace, Provider()).run_once()
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == task.state == "failed"
    assert run.last_error_code == expected
    assert run.assistant_message_id is None
    assert events[-1].type == "run.failed"


async def test_event_limit_during_retry_becomes_failure_not_stuck_lease(workspace):
    first = await submit(workspace)
    await frozen_limits(workspace, first["run_id"], max_regular_events=6)

    class Provider:
        async def stream_request(self, request):
            yield "draft"
            raise TransientTaskError("UPSTREAM_TEMPORARY", "retry")

    assert await runtime(workspace, Provider()).run_once()
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == task.state == "failed"
    assert run.last_error_code == "RUN_EVENT_LIMIT"
    assert events[-1].type == "run.failed"


@pytest.mark.parametrize("mode", ["empty", "whitespace", "protocol"])
async def test_empty_or_invalid_provider_stream_cannot_succeed(workspace, mode):
    first = await submit(workspace)

    class Provider:
        async def stream_request(self, request):
            if mode == "whitespace":
                yield "  "
            elif mode == "protocol":
                yield 42
            elif False:
                yield ""

    assert await runtime(workspace, Provider()).run_once()
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == task.state == "failed"
    assert run.last_error_code == (
        "MODEL_STREAM_INVALID" if mode == "protocol" else "MODEL_EMPTY_OUTPUT"
    )
    assert run.assistant_message_id is None


async def test_expired_cancellation_ack_rejected_reclaimer_cancels_not_fails(
    workspace, monkeypatch
):
    first = await submit(workspace)
    settings, factory, *_ = workspace
    async with factory() as session:
        task = await queue.claim_next_task(session, "w", settings)
        await cancel_session_run(session, settings, first["run_id"])
    future = queue.utc_now() + timedelta(seconds=700)
    monkeypatch.setattr(queue, "utc_now", lambda: future)
    async with factory() as session:
        assert not await queue.acknowledge_cancellation(session, first["task_id"], "w", 1)
    async with factory() as session:
        assert await queue.requeue_expired(session) == 1
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == task.state == "cancelled"
    assert not any(e.type == "run.failed" for e in events)


@pytest.mark.parametrize("cancel_first", [True, False])
async def test_cancel_success_transaction_order_has_one_terminal(workspace, cancel_first):
    first = await submit(workspace)
    settings, factory, *_ = workspace
    async with factory() as session:
        await queue.claim_next_task(session, "w", settings)
        await queue.mark_running(session, first["task_id"], "w", 1)
    if cancel_first:
        async with factory() as session:
            await cancel_session_run(session, settings, first["run_id"])
        async with factory() as session:
            with pytest.raises(ExecutionStopped):
                await complete_run(session, first["task_id"], "w", 1, "late", [])
        async with factory() as session:
            assert await queue.acknowledge_cancellation(session, first["task_id"], "w", 1)
    else:
        async with factory() as session:
            await complete_run(session, first["task_id"], "w", 1, "answer", [])
        async with factory() as session:
            assert (
                await cancel_session_run(session, settings, first["run_id"])
            ).status == "succeeded"
    run, task, events = await facts(workspace, first["run_id"])
    assert run.status == task.state == ("cancelled" if cancel_first else "succeeded")
    assert (
        len([e for e in events if e.type in {"run.succeeded", "run.cancelled", "run.failed"}]) == 1
    )


async def test_successful_explicit_retry_turn_survives_failed_creator_context(workspace):
    first = await submit(workspace, "original failed input")
    settings, factory, *_ = workspace
    async with factory() as session:
        await cancel_session_run(session, settings, first["run_id"])
        retry, _ = await create_related_run(
            session, settings, first["run_id"], RunOperationCreate(), "retry", "retry"
        )

    class Provider:
        def __init__(self):
            self.requests = []

        async def stream_request(self, request):
            self.requests.append(request)
            yield "retry answer"

    provider = Provider()
    worker = runtime(workspace, provider)
    assert await worker.run_once()
    await submit(workspace, "followup", 2, "followup")
    assert await worker.run_once()
    sent = [(m.role, m.content) for m in provider.requests[-1].messages]
    assert ("user", "original failed input") in sent
    assert ("assistant", "retry answer") in sent


async def test_cancelled_standalone_input_is_recorded_as_omitted(workspace):
    first = await submit(workspace, "cancelled standalone")
    settings, factory, *_ = workspace
    async with factory() as session:
        await cancel_session_run(session, settings, first["run_id"])
    second = await submit(workspace, "next", 1, "next")
    assert await runtime(workspace).run_once()
    async with factory() as session:
        detail = await context_detail(session, settings, second["run_id"])
        assert {"message_id": first["message_id"], "reason": "incomplete_turn"} in detail["plan"][
            "omitted_messages"
        ]


async def test_plan_publication_after_last_flush_lease_expiry_rolls_back(workspace, monkeypatch):
    first = await submit(workspace)
    from sqlalchemy.ext.asyncio import AsyncSession

    original = AsyncSession.flush
    original_clock = queue.utc_now

    async def expire_after_plan_flush(session, *args, **kwargs):
        has_plan = any(isinstance(value, ContextPlanModel) for value in session.new)
        await original(session, *args, **kwargs)
        if has_plan:
            future = original_clock() + timedelta(seconds=700)
            monkeypatch.setattr(queue, "utc_now", lambda: future)

    monkeypatch.setattr(AsyncSession, "flush", expire_after_plan_flush)
    assert await runtime(workspace).run_once()
    settings, factory, *_ = workspace
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(ContextPlanModel)) == 0
        run = await session.get(RunModel, first["run_id"])
        assert run.context_plan_id is None and run.assistant_message_id is None
        assert not any(
            e.type in {"context.planned", "run.succeeded"}
            for e in await list_events(session, run.run_id)
        )


async def test_summary_extraction_failure_publishes_trim_only_and_safe_log(
    workspace, monkeypatch, caplog
):
    settings, factory, tid, bid = workspace
    await submit(workspace, "! " * 2500)

    class Provider:
        async def stream_request(self, request):
            yield "answer"

    worker = runtime(workspace, Provider())
    assert await worker.run_once()
    # 第二次 mandatory 可容纳，但两个完整旧轮次无法同时放入小窗口。
    async with factory() as session:
        profile = await session.get(ModelProfileModel, ("mock-default", 1))
        profile.context_window_tokens = 2048
        profile.max_output_tokens = 256
        await session.commit()
    second = await submit(workspace, "followup", 2, "next")

    def fail(*args):
        raise ValueError("PRIVATE SUMMARY TEXT")

    monkeypatch.setattr("backend.application.context._extract_summary", fail)
    assert await worker.run_once()
    async with factory() as session:
        context = await context_detail(session, settings, second["run_id"])
        assert context["plan"]["trim_policy_version"] == "trim_only_v1"
    assert "SUMMARY_EXTRACTION_FAILED" in caplog.text
    assert "PRIVATE SUMMARY TEXT" not in caplog.text


async def test_worker_real_http_uses_frozen_model_and_planned_history(
    workspace, provider_server, monkeypatch
):
    url, observed = provider_server
    settings, factory, *_ = workspace
    first = await submit(workspace, "history sentinel")
    assert await runtime(workspace).run_once()
    monkeypatch.setenv("MODEL_API_KEY", "private-http-key")
    async with factory() as session:
        session.add(
            ModelProfileModel(
                profile_id="http",
                version=1,
                display_name="HTTP",
                provider_kind="openai_compatible",
                model_name="selected-http-model",
                generation_params={"temperature": 0.2},
                base_url=url,
                context_window_tokens=8192,
                max_output_tokens=77,
                status="enabled",
                is_default=False,
                tokenizer_kind="tiktoken",
                tokenizer_version="calibrated-1",
                tokenizer_config={
                    "safety_margin_tokens": 128,
                    "summary_max_tokens": 512,
                    "encoding_name": "cl100k_base",
                    "message_overhead_tokens": 4,
                    "request_overhead_tokens": 2,
                    "calibration_version": "test1",
                },
                config_ref="env:MODEL_API_KEY",
            )
        )
        await session.commit()
        thread_id, branch_id = workspace[2:]
        result, _ = await create_session_message(
            session,
            settings,
            thread_id,
            MessageCreate(
                branch_id=branch_id,
                content="HTTP question",
                expected_version=2,
                model_profile_id="http",
                model_profile_version=1,
            ),
            "http",
        )
        profile = await session.get(ModelProfileModel, ("http", 1))
        profile.status = "disabled"
        await session.commit()
    settings.model_name = "must-not-use-current-settings"
    assert await runtime(workspace).run_once()
    run, _, _ = await facts(workspace, result["run_id"])
    assert run.status == "succeeded", run.last_error_code
    payload = observed[-1]
    assert payload["model"] == "selected-http-model"
    assert payload["max_tokens"] == 77 and payload["temperature"] == 0.2
    assert {"role": "user", "content": "history sentinel"} in payload["messages"]
    assert payload["messages"][-1] == {"role": "user", "content": "HTTP question"}
    async with factory() as session:
        context = await context_detail(session, settings, run.run_id)
        assert first["message_id"] in context["plan"]["selected_message_ids"]


async def test_worker_embedding_rebuild_uses_frozen_endpoint_and_kind(
    workspace, provider_server, monkeypatch
):
    # 生成Profile独立于Embedding；重启后改Settings不能改变旧Run的检索向量来源。
    url, observed = provider_server
    settings, *_ = workspace
    settings.mock_provider = False
    settings.model_base_url = url
    settings.model_api_key = "runtime-embedding-key"
    settings.model_name = "unused-generation-name"
    settings.embedding_model_name = "frozen-embedding-model"
    monkeypatch.setenv("MODEL_API_KEY", "runtime-embedding-key")
    created = await submit(workspace, "frozen embedding question")
    settings.model_base_url = "http://127.0.0.1:1/changed"
    settings.embedding_model_name = "changed-model"
    assert await runtime(workspace).run_once()
    run, _, _ = await facts(workspace, created["run_id"])
    assert run.status == "succeeded", run.last_error_code
    assert observed == [{"model": "frozen-embedding-model", "input": "frozen embedding question"}]
    retrieval = run.snapshot_json["retrieval"]
    assert retrieval["embedding_provider_kind"] == "openai_compatible"
    assert retrieval["embedding_base_url"] == url
    assert retrieval["embedding_config_ref"] == "env:MODEL_API_KEY"
    assert "runtime-embedding-key" not in str(run.snapshot_json)


async def test_mock_embedding_mode_does_not_depend_on_embedding_model_label(workspace):
    settings, *_ = workspace
    settings.embedding_model_name = "configured-but-unused-in-mock-mode"
    created = await submit(workspace)
    assert await runtime(workspace).run_once()
    run, _, _ = await facts(workspace, created["run_id"])
    assert run.status == "succeeded", run.last_error_code
    assert run.snapshot_json["retrieval"]["embedding_provider_kind"] == "mock"


async def test_regenerate_worker_sees_input_prefix_without_old_answer_or_future(workspace):
    class Provider:
        def __init__(self):
            self.requests = []

        async def stream_request(self, request):
            self.requests.append(request)
            yield "old answer sentinel" if len(self.requests) == 1 else "new answer"

    provider = Provider()
    worker = runtime(workspace, provider)
    first = await submit(workspace, "original user sentinel")
    assert await worker.run_once()
    await submit(workspace, "parent future sentinel", 2, "future")
    assert await worker.run_once()
    settings, factory, *_ = workspace
    async with factory() as session:
        child, _ = await create_related_run(
            session, settings, first["run_id"], RunOperationCreate(), "regen", "regenerate"
        )
    assert await worker.run_once()
    sent = "|".join(m.content for m in provider.requests[-1].messages)
    assert "original user sentinel" in sent
    assert "old answer sentinel" not in sent and "parent future sentinel" not in sent
    async with factory() as session:
        plan = (await context_detail(session, settings, child["run_id"]))["plan"]
        assert plan["branch_id"] == child["branch_id"]
        assert plan["selected_message_ids"] == []


@pytest.mark.parametrize("boundary", ["lease", "deadline"])
async def test_v2_final_publication_expiry_rolls_back_message_events_and_head(
    workspace, monkeypatch, boundary
):
    from sqlalchemy.ext.asyncio import AsyncSession

    first = await submit(workspace)
    settings, factory, tid, bid = workspace
    async with factory() as session:
        task = await queue.claim_next_task(session, "w", settings)
        await queue.mark_running(session, task.task_id, "w", 1)
        run = await session.get(RunModel, first["run_id"])
        branch = await session.get(BranchModel, bid)
        before = (run.next_event_seq, branch.head_message_id, branch.version)
    original = AsyncSession.flush

    async def expire_after_terminal(session, *args, **kwargs):
        from backend.db.models import RunEventModel

        hit = any(
            isinstance(value, RunEventModel) and value.type == "run.succeeded"
            for value in session.new
        )
        await original(session, *args, **kwargs)
        if hit:
            expires = task.lease_expires_at if boundary == "lease" else task.deadline_at
            future = expires.replace(tzinfo=timezone.utc) + timedelta(seconds=1)
            monkeypatch.setattr(queue, "utc_now", lambda: future)

    monkeypatch.setattr(AsyncSession, "flush", expire_after_terminal)
    async with factory() as session:
        with pytest.raises(ExecutionStopped):
            await complete_run(session, task.task_id, "w", 1, "late", [])
    async with factory() as session:
        run = await session.get(RunModel, first["run_id"])
        branch = await session.get(BranchModel, bid)
        assert (run.next_event_seq, branch.head_message_id, branch.version) == before
        assert run.assistant_message_id is None
        assert (
            await session.scalar(
                select(func.count())
                .select_from(MessageModel)
                .where(MessageModel.role == "assistant")
            )
            == 0
        )


@pytest.mark.parametrize("boundary", ["step_timeout_seconds", "stream_timeout_seconds"])
async def test_frozen_timeout_closes_stream_and_never_publishes_success(workspace, boundary):
    first = await submit(workspace)
    await frozen_limits(workspace, first["run_id"], **{boundary: 1})
    closed = asyncio.Event()

    class Provider:
        async def stream_request(self, request):
            try:
                yield "draft"
                await asyncio.Event().wait()
            finally:
                closed.set()

    worker = runtime(workspace, Provider())
    await asyncio.wait_for(worker.run_once(), 3)
    run, task, events = await facts(workspace, first["run_id"])
    assert closed.is_set()
    assert run.status == task.state == "retry_waiting"
    assert run.assistant_message_id is None
    assert not any(e.type == "run.succeeded" for e in events)


async def test_persisted_summary_has_exact_sources_safe_projection_and_compacted_event(workspace):
    import hashlib
    import json

    from backend.db.models import ConversationSummaryModel

    question = "source " * 2500
    first = await submit(workspace, question)

    class Provider:
        async def stream_request(self, request):
            yield "answer"

    worker = runtime(workspace, Provider())
    assert await worker.run_once()
    settings, factory, *_ = workspace
    async with factory() as session:
        profile = await session.get(ModelProfileModel, ("mock-default", 1))
        profile.context_window_tokens = 2048
        profile.max_output_tokens = 256
        await session.commit()
    second = await submit(workspace, "followup", 2, "summary")
    assert await worker.run_once()
    run, _, events = await facts(workspace, second["run_id"])
    assert run.status == "succeeded"
    async with factory() as session:
        detail = await context_detail(session, settings, run.run_id)
        summaries = detail["plan"]["summaries"]
        assert len(summaries) == 1
        summary = await session.get(ConversationSummaryModel, summaries[0]["summary_id"])
        assert summary.covered_message_ids[0] == first["message_id"]
        assert summary.source_segments[0] == {
            "message_id": first["message_id"],
            "start_offset": 0,
            "end_offset": 128,
        }
        sources = []
        for identity in summary.covered_message_ids:
            message = await session.get(MessageModel, identity)
            sources.append((message.message_id, message.content))
        assert (
            summary.source_hash
            == hashlib.sha256(json.dumps(sources, ensure_ascii=False).encode()).hexdigest()
        )
        assert summary.summary_text not in str(detail)
        assert summaries[0]["source_run_id"] == run.run_id
    assert len([e for e in events if e.type == "context.compacted"]) == 1
