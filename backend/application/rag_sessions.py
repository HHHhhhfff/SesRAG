"""schema3快照及安全投影；复用原会话创建／分支事务。"""

from copy import deepcopy

from sqlalchemy import select

from backend.application.errors import ApplicationError
from backend.application.retrieval_views import freeze_retrieval, load_scope
from backend.db.rag_models import RetrievalExecutionModel, RetrievalViewModel


async def upgrade_snapshot(session, settings, snapshot, selection, source=None):
    snapshot = deepcopy(snapshot)
    if source is not None and source.execution_schema_version == 3:
        rag = deepcopy(source.snapshot_json["rag"])
        if rag["enabled"]:
            await load_scope(session, settings, rag["view_id"])
    elif selection is not None and selection.enabled:
        if not selection.knowledge_base_id:
            raise ApplicationError("INVALID_RAG_PARAMETER", "开启RAG须选择知识库", 422)
        scope, config = await freeze_retrieval(session, settings, selection)
        rag = {"enabled": True, "view_id": scope.view_id, "config": config}
    else:
        if selection and (
            selection.knowledge_base_id
            or selection.retrieval_profile_id
            or selection.filters.model_dump(exclude_defaults=True)
            or selection.overrides.model_dump(exclude_none=True)
        ):
            raise ApplicationError("INVALID_RAG_PARAMETER", "关闭RAG不能混入检索参数", 422)
        rag = {"enabled": False}
    snapshot["schema_version"], snapshot["rag"] = 3, rag
    # 原生成Provider只消费旧retrieval兼容字段，不用它执行schema3检索。
    snapshot["retrieval"]["enabled"] = False
    return snapshot


def generation_snapshot(snapshot):
    if snapshot.get("schema_version") != 3 or set(snapshot) != {
        "schema_version",
        "owner_id",
        "thread_id",
        "branch_id",
        "input_anchor",
        "model_profile",
        "prompt",
        "context",
        "retrieval",
        "execution",
        "rag",
    }:
        raise ApplicationError("INVALID_RUN_SNAPSHOT", "schema3快照字段无效", 422)
    from backend.domain.rag_snapshot import RAG_BINDING

    try:
        rag = RAG_BINDING.validate_python(snapshot["rag"])
        if rag.enabled and rag.view_id != rag.config.view_id:
            raise ValueError()
    except ValueError:
        raise ApplicationError("INVALID_RUN_SNAPSHOT", "schema3工具绑定无效", 422) from None
    value = deepcopy(snapshot)
    value.pop("rag")
    value["schema_version"] = 2
    return value


async def run_detail(session, settings, identity):
    from backend.api.schemas.v2.models import ModelSelection
    from backend.api.schemas.v2.runs import TaskSummary
    from backend.application.session_runs import load_session_run, plan_summary, utc_projection
    from backend.db.models import ContextPlanModel

    run, task = await load_session_run(session, settings, identity, allow_v3=True)
    rag = run.snapshot_json.get("rag") if run.execution_schema_version == 3 else None
    summary = None
    if rag is not None:
        execution = await session.scalar(
            select(RetrievalExecutionModel)
            .where(RetrievalExecutionModel.run_id == run.run_id)
            .order_by(RetrievalExecutionModel.generation.desc())
            .limit(1)
        )
        summary = {
            "enabled": rag["enabled"],
            "execution_state": (
                {"succeeded": "completed", "interrupted": "failed"}.get(
                    execution.state, execution.state
                )
                if execution
                else "not_started"
            ),
            "result_mode": execution.mode if execution else None if rag["enabled"] else "off",
            "error_code": execution.error_code if execution else run.last_error_code,
        }
        if rag["enabled"]:
            view = await session.get(RetrievalViewModel, rag["view_id"])
            summary.update(
                view_id=rag["view_id"],
                knowledge_base_id=view.knowledge_base_id,
                retrieval_profile_id=rag["config"]["retrieval_profile"]["profile_id"],
                top_k=rag["config"]["policy"]["top_k"],
                embedding_dimensions=rag["config"]["embedding"]["config"]["space"]["dimension"],
            )
    profile = run.snapshot_json.get("model_profile")
    context = run.snapshot_json.get("context", {})
    snapshot_summary = (
        None
        if not profile
        else {
            "schema_version": run.execution_schema_version,
            "context_policy_version": context["trim_policy_version"],
            "counter_version": context["counter_version"],
            "context_window_tokens": profile["context_window_tokens"],
            "reserved_output_tokens": profile["max_output_tokens"],
            "safety_margin_tokens": context["safety_margin_tokens"],
        }
    )
    plan = await session.get(ContextPlanModel, run.context_plan_id) if run.context_plan_id else None
    return utc_projection(
        {
            **{
                name: getattr(run, name)
                for name in (
                    "run_id",
                    "thread_id",
                    "branch_id",
                    "user_message_id",
                    "assistant_message_id",
                    "parent_run_id",
                    "operation_kind",
                    "execution_schema_version",
                    "status",
                    "last_error_code",
                    "created_at",
                    "updated_at",
                )
            },
            "model": {name: profile[name] for name in ModelSelection.model_fields}
            if profile
            else None,
            "task": {name: getattr(task, name) for name in TaskSummary.model_fields},
            "rag_summary": summary,
            "legacy": run.execution_schema_version == 1,
            "snapshot": snapshot_summary,
            "context_plan": plan_summary(plan) if plan else None,
        }
    )
