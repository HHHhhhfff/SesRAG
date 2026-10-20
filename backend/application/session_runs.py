"""v2 Run 创建、显式操作及安全事实投影。"""

from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select

from backend.api.schemas.v2.context import ContextPlan as ContextProjection
from backend.api.schemas.v2.context import SummaryMetadata
from backend.api.schemas.v2.models import ModelSelection
from backend.api.schemas.v2.runs import RunResponse, TaskSummary
from backend.application.branches import (
    ACTIVE_RUN_STATES,
    MAX_BRANCH_DEPTH,
    MAX_BRANCHES,
    resolve_scope,
)
from backend.application.errors import ApplicationError
from backend.application.model_profiles import profile_reason
from backend.application.runs import event_to_dict
from backend.application.session_operations import record_operation, replay_operation, request_hash
from backend.application.session_threads import utc_projection
from backend.application.threads import get_thread, now_utc, upgrade_for_v2_write
from backend.db.models import (
    BranchModel,
    ContextPlanModel,
    ConversationSummaryModel,
    MessageModel,
    RunEventModel,
    RunModel,
    TaskModel,
    ThreadModel,
)
from backend.infrastructure.events.journal import append_event
from backend.infrastructure.providers.context_counter import token_counter_from_profile
from backend.infrastructure.providers.registry import (
    EXECUTION_SNAPSHOT_LIMITS,
    build_snapshot2,
    profile_snapshot,
)
from backend.infrastructure.queue import postgres_queue as queue
from backend.infrastructure.session.branches import SQLBranchRepository
from backend.infrastructure.session.model_profiles import SQLModelProfileRepository


async def load_session_run(session, settings, run_id):
    run = await session.get(RunModel, run_id)
    thread = await session.get(ThreadModel, run.thread_id) if run else None
    if thread is None or thread.owner_id != settings.owner_id:
        raise ApplicationError("RUN_NOT_FOUND", "Run 不存在", 404)
    task = await session.get(TaskModel, run.primary_task_id)
    if task is None:
        raise ApplicationError("RUN_NOT_FOUND", "Run 不存在", 404)
    return run, task


async def select_profile(session, payload, source=None):
    repository = SQLModelProfileRepository(session)
    identity, version = payload.model_profile_id, payload.model_profile_version
    if identity is None and source is not None:
        if source.execution_schema_version == 1:
            raise ApplicationError("MODEL_PROFILE_REQUIRED", "旧 Run 必须显式选择模型", 422)
        identity, version = source.model_profile_id, source.model_profile_version
    if identity is None:
        profiles = await repository.list_profiles()
        profile = next((p for p in profiles if p.is_default), None)
    else:
        profile = await repository.get_profile(identity, version)
    if profile is None or profile_reason(profile):
        raise ApplicationError("MODEL_PROFILE_UNAVAILABLE", "模型配置不可用于新 Run", 409)
    return profile


def new_snapshot(settings, thread, branch, message, profile, source=None):
    frozen = profile_snapshot(profile)
    counter = token_counter_from_profile(frozen)
    context = {
        "trim_policy_version": "trim_then_extract_v1",
        "summary_max_tokens": profile.tokenizer_config["summary_max_tokens"],
        "safety_margin_tokens": profile.tokenizer_config["safety_margin_tokens"],
        "max_candidate_messages": 200,
        "max_candidate_chars": 200_000,
        "counter_version": counter.version,
    }
    execution = dict(EXECUTION_SNAPSHOT_LIMITS)
    execution["max_attempts"] = min(settings.task_max_attempts, 3)
    execution["deadline_seconds"] = min(settings.task_deadline, 600)
    retrieval = {
        "enabled": True,
        "top_k": settings.rag_top_k,
        "embedding_dimensions": 384,
        "embedding_model": "mock-384" if settings.mock_provider else settings.embedding_model_name,
        "embedding_provider_kind": "mock" if settings.mock_provider else "openai_compatible",
        "embedding_base_url": None if settings.mock_provider else settings.model_base_url,
        "embedding_config_ref": None if settings.mock_provider else "env:MODEL_API_KEY",
    }
    prompt = {"version": "rag_v1"}
    if source is not None and source.execution_schema_version == 2:
        old = source.snapshot_json
        context = deepcopy(old["context"])
        # 显式换模型只替换与新 Profile 绑定的预算和计数器。
        context.update(
            summary_max_tokens=profile.tokenizer_config["summary_max_tokens"],
            safety_margin_tokens=profile.tokenizer_config["safety_margin_tokens"],
            counter_version=counter.version,
        )
        execution, retrieval, prompt = (
            deepcopy(old[key]) for key in ("execution", "retrieval", "prompt")
        )
        if payload_same_profile(source, profile):
            frozen = deepcopy(old["model_profile"])
    return build_snapshot2(
        owner_id=thread.owner_id,
        thread_id=thread.thread_id,
        branch_id=branch.branch_id,
        input_anchor={"message_id": message.message_id, "seq": message.seq},
        profile=frozen,
        prompt=prompt,
        retrieval=retrieval,
        context=context,
        execution=execution,
    )


def payload_same_profile(source, profile):
    return (source.model_profile_id, source.model_profile_version) == (
        profile.profile_id,
        profile.version,
    )


def operation_result(run):
    return {
        "branch_id": run.branch_id,
        "message_id": run.user_message_id,
        "run_id": run.run_id,
        "task_id": run.primary_task_id,
        "status": run.status,
    }


async def insert_run(session, settings, thread, branch, message, profile, kind, source=None):
    snapshot = new_snapshot(settings, thread, branch, message, profile, source)
    run = RunModel(
        run_id=str(uuid4()),
        thread_id=thread.thread_id,
        branch_id=branch.branch_id,
        user_message_id=message.message_id,
        parent_run_id=source.run_id if source else None,
        operation_kind=kind,
        execution_schema_version=2,
        status="queued",
        snapshot_json=snapshot,
        model_profile_id=profile.profile_id,
        model_profile_version=profile.version,
    )
    session.add(run)
    await session.flush()
    task = TaskModel(
        task_id=str(uuid4()),
        kind="run",
        run_id=run.run_id,
        state="queued",
        max_attempts=snapshot["execution"]["max_attempts"],
        deadline_at=now_utc() + timedelta(seconds=snapshot["execution"]["deadline_seconds"]),
    )
    session.add(task)
    await session.flush()
    run.primary_task_id = task.task_id
    if source is None:
        message.run_id = run.run_id
    await session.flush()
    await append_event(
        session,
        run.run_id,
        "run.created",
        {"message_id": message.message_id, "branch_id": branch.branch_id, "operation_kind": kind},
    )
    await append_event(session, run.run_id, "task.queued", {})
    if source:
        await append_event(
            session,
            run.run_id,
            "run.retry_created" if kind == "user_retry" else "run.regenerated",
            {
                "parent_run_id": source.run_id,
                "branch_id": branch.branch_id,
                "user_message_id": message.message_id,
            },
        )
    thread.updated_at = now_utc()
    return run, task


async def create_session_message(session, settings, thread_id, payload, key):
    thread = await get_thread(session, settings, thread_id)
    await session.refresh(thread, with_for_update=True)
    digest = request_hash(
        "message",
        payload.model_dump(exclude_unset=True),
        ("model_profile_id", "model_profile_version"),
    )
    replay = await replay_operation(session, thread_id, key, digest)
    if replay:
        return operation_result(await session.get(RunModel, replay.result_run_id)), True
    branch = await session.scalar(
        select(BranchModel)
        .where(BranchModel.thread_id == thread_id, BranchModel.branch_id == payload.branch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if branch is None:
        raise ApplicationError("BRANCH_NOT_FOUND", "Branch 不存在", 404)
    if thread.archived_at is not None:
        raise ApplicationError("THREAD_ARCHIVED", "Thread 已归档", 409)
    if branch.version != payload.expected_version:
        raise ApplicationError("BRANCH_HEAD_CHANGED", "Branch 末尾已变化", 409)
    if await branch_busy(session, branch.branch_id):
        raise ApplicationError("BRANCH_BUSY", "Branch 存在活动 Run", 409)
    profile = await select_profile(session, payload)
    await upgrade_for_v2_write(session, thread)
    thread.next_message_seq += 1
    message = MessageModel(
        message_id=str(uuid4()),
        thread_id=thread_id,
        branch_id=branch.branch_id,
        seq=thread.next_message_seq,
        role="user",
        source="user_input",
        content=payload.content,
        status="completed",
    )
    session.add(message)
    await session.flush()
    branch.head_message_id = message.message_id
    branch.version += 1
    run, task = await insert_run(
        session,
        settings,
        thread,
        branch,
        message,
        profile,
        "branch_continue" if branch.parent_branch_id else "initial",
    )
    record_operation(
        session,
        thread_id,
        key,
        "message",
        digest,
        branch_id=branch.branch_id,
        message_id=message.message_id,
        run_id=run.run_id,
        task_id=task.task_id,
    )
    await session.commit()
    return operation_result(run), False


async def branch_busy(session, branch_id):
    return await session.scalar(
        select(RunModel.run_id).where(
            RunModel.branch_id == branch_id, RunModel.status.in_(ACTIVE_RUN_STATES)
        )
    )


async def create_related_run(session, settings, run_id, payload, key, kind):
    source, _ = await load_session_run(session, settings, run_id)
    thread = await get_thread(session, settings, source.thread_id)
    await session.refresh(thread, with_for_update=True)
    digest = request_hash(
        kind,
        {"run_id": run_id, **payload.model_dump(exclude_unset=True)},
        ("model_profile_id", "model_profile_version"),
    )
    replay = await replay_operation(session, thread.thread_id, key, digest)
    if replay:
        return operation_result(await session.get(RunModel, replay.result_run_id)), True
    if thread.archived_at is not None:
        raise ApplicationError("THREAD_ARCHIVED", "Thread 已归档", 409)
    # 来源只读，不能在持有 Thread 锁后再反锁旧 Run/Task。
    await session.refresh(source)
    if source.status not in ({"failed", "cancelled"} if kind == "retry" else {"succeeded"}):
        raise ApplicationError("INVALID_RUN_STATE", "Run 状态不允许此操作", 409)
    profile = await select_profile(session, payload, source)
    repository = SQLBranchRepository(session)
    scope = await resolve_scope(repository, thread.thread_id, source.branch_id)
    await repository.lock_branches(thread.thread_id, [b.branch_id for b in scope.branches])
    branch = await session.get(BranchModel, source.branch_id)
    await session.refresh(branch)
    message = await session.get(MessageModel, source.user_message_id)
    anchor = await repository.list_path_messages(
        thread.thread_id, scope.segments, message_id=message.message_id, limit=1
    )
    if not anchor or message.role != "user":
        raise ApplicationError("INVALID_BRANCH_PATH", "Run 输入不在路径", 422)
    reuse = (
        kind == "retry"
        and branch.head_message_id == message.message_id
        and not await branch_busy(session, branch.branch_id)
    )
    if not reuse:
        count = await session.scalar(
            select(func.count())
            .select_from(BranchModel)
            .where(BranchModel.thread_id == thread.thread_id)
        )
        if count >= MAX_BRANCHES or len(scope.branches) >= MAX_BRANCH_DEPTH:
            raise ApplicationError("BRANCH_LIMIT_EXCEEDED", "Branch 数量或深度已达上限", 422)
        branch = BranchModel(
            branch_id=str(uuid4()),
            thread_id=thread.thread_id,
            parent_branch_id=source.branch_id,
            fork_message_id=message.message_id,
            name=f"分支 {count + 1}",
            is_default=False,
            head_message_id=message.message_id,
            version=0,
        )
        session.add(branch)
        await session.flush()
    await upgrade_for_v2_write(session, thread)
    run, task = await insert_run(
        session,
        settings,
        thread,
        branch,
        message,
        profile,
        "user_retry" if kind == "retry" else "regenerate",
        source,
    )
    record_operation(
        session,
        thread.thread_id,
        key,
        kind,
        digest,
        branch_id=branch.branch_id,
        message_id=message.message_id,
        run_id=run.run_id,
        task_id=task.task_id,
    )
    await session.commit()
    return operation_result(run), False


async def cancel_session_run(session, settings, run_id):
    run, task = await load_session_run(session, settings, run_id)
    if run.execution_schema_version == 1:
        from backend.application.runs import cancel_run

        return await cancel_run(session, settings, run_id)
    task = await queue.lock_task(session, task.task_id)
    run = await queue.lock_run(session, run_id)
    if run.status in queue.TERMINAL or run.status == "cancelling":
        return run
    run.cancel_requested_at = now_utc()
    if task.state in queue.ACTIVE:
        run.status = "cancelling"
        event = "run.cancelling"
    else:
        run.status = task.state = "cancelled"
        task.lease_expires_at = None
        event = "run.cancelled"
    await append_event(session, run_id, event, {"reason": "user_requested"})
    await session.commit()
    return run


def plan_summary(plan):
    return {
        **{
            name: getattr(plan, name)
            for name in (
                "context_plan_id",
                "generation",
                "attempt",
                "estimated_input_tokens",
                "reserved_output_tokens",
                "safety_margin_tokens",
                "context_window_tokens",
                "status",
            )
        },
        "selected_message_count": len(plan.selected_message_ids),
        "omitted_message_count": sum(r["count"] for r in plan.omitted_ranges)
        + sum(1 for m in plan.omitted_messages if m["reason"] == "incomplete_turn"),
        "summary_count": len(plan.summary_ids),
    }


def summary_projection(summary):
    return {name: getattr(summary, name) for name in SummaryMetadata.model_fields}


async def context_detail(session, settings, run_id, generation=None):
    run, task = await load_session_run(session, settings, run_id)
    statement = select(ContextPlanModel).where(ContextPlanModel.run_id == run_id)
    if generation is not None:
        statement = statement.where(ContextPlanModel.generation == generation)
    else:
        statement = statement.where(ContextPlanModel.context_plan_id == run.context_plan_id)
    plan = await session.scalar(statement)
    if plan is None:
        if generation is not None:
            raise ApplicationError("CONTEXT_PLAN_NOT_FOUND", "计划不存在", 404)
        return {"plan": None, "reason": "not_planned"}
    summaries = (
        await session.scalars(
            select(ConversationSummaryModel).where(
                ConversationSummaryModel.summary_id.in_(plan.summary_ids)
            )
        )
    ).all()
    result = {
        name: getattr(plan, name) for name in ContextProjection.model_fields if name != "summaries"
    }
    result["summaries"] = [summary_projection(s) for s in summaries]
    return utc_projection({"plan": result, "reason": None})


async def session_run_detail(session, settings, run_id):
    run, task = await load_session_run(session, settings, run_id)
    legacy = run.execution_schema_version == 1
    result = {name: getattr(run, name) for name in RunResponse.model_fields if hasattr(run, name)}
    result.update(
        legacy=legacy,
        model=None,
        snapshot=None,
        context_plan=None,
        task={name: getattr(task, name) for name in TaskSummary.model_fields},
    )
    if not legacy:
        snapshot = run.snapshot_json
        profile, context, retrieval = (
            snapshot["model_profile"],
            snapshot["context"],
            snapshot["retrieval"],
        )
        result["model"] = {name: profile[name] for name in ModelSelection.model_fields}
        result["snapshot"] = {
            "schema_version": 2,
            "prompt_version": snapshot["prompt"]["version"],
            "context_policy_version": context["trim_policy_version"],
            "summary_policy_version": context["trim_policy_version"],
            "counter_version": context["counter_version"],
            "context_window_tokens": profile["context_window_tokens"],
            "reserved_output_tokens": profile["max_output_tokens"],
            "safety_margin_tokens": context["safety_margin_tokens"],
            "retrieval_enabled": retrieval["enabled"],
            "retrieval_top_k": retrieval["top_k"],
            "embedding_dimensions": 384,
        }
        if run.context_plan_id:
            result["context_plan"] = plan_summary(
                await session.get(ContextPlanModel, run.context_plan_id)
            )
    return utc_projection(result)


async def session_run_events(session, settings, run_id, after_seq=0, limit=200):
    await load_session_run(session, settings, run_id)
    rows = list(
        (
            await session.scalars(
                select(RunEventModel)
                .where(RunEventModel.run_id == run_id, RunEventModel.seq > after_seq)
                .order_by(RunEventModel.seq)
                .limit(limit + 1)
            )
        ).all()
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return {
        "events": [event_to_dict(e) for e in rows],
        "has_more": more,
        "next_after_seq": rows[-1].seq if rows else after_seq,
    }
