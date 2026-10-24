"""阶段 1 迁移只读预检；不导入可变 ORM。"""

import json

import sqlalchemy as sa
from alembic import context


def preflight(bind):
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text("LOCK TABLE threads,messages,runs,tasks,run_events IN ACCESS EXCLUSIVE MODE")
        )
    checks = (
        (
            "RUN_INPUT_CONFLICT",
            "SELECT r.run_id FROM runs r LEFT JOIN messages m ON m.message_id=r.user_message_id "
            "WHERE m.message_id IS NULL OR m.role<>'user' OR m.thread_id<>r.thread_id",
        ),
        (
            "RUN_TASK_CONFLICT",
            "SELECT r.run_id FROM runs r LEFT JOIN tasks t ON t.run_id=r.run_id AND t.kind='run' "
            "GROUP BY r.run_id,r.primary_task_id HAVING COUNT(t.task_id)<>1 "
            "OR MAX(t.task_id)<>r.primary_task_id OR r.primary_task_id IS NULL",
        ),
        (
            "RUN_ASSISTANT_CONFLICT",
            "SELECT r.run_id FROM runs r LEFT JOIN messages m "
            "ON m.message_id=r.assistant_message_id WHERE r.assistant_message_id IS NOT NULL "
            "AND (m.message_id IS NULL OR m.role<>'assistant' OR m.thread_id<>r.thread_id "
            "OR m.run_id IS NULL OR m.run_id<>r.run_id)",
        ),
        (
            "ASSISTANT_POINTER_CONFLICT",
            "SELECT m.message_id FROM messages m LEFT JOIN runs r ON r.run_id=m.run_id "
            "WHERE m.role='assistant' AND m.run_id IS NOT NULL AND (r.run_id IS NULL "
            "OR r.assistant_message_id IS NULL OR r.assistant_message_id<>m.message_id)",
        ),
        (
            "ACTIVE_BRANCH_CONFLICT",
            "SELECT thread_id FROM runs WHERE "
            "status IN ('queued','running','retry_waiting','cancelling') "
            "GROUP BY thread_id HAVING COUNT(*)>1",
        ),
        (
            "STALE_MESSAGE_COUNTER",
            "SELECT t.thread_id FROM threads t JOIN messages m ON t.thread_id=m.thread_id "
            "GROUP BY t.thread_id,t.next_message_seq HAVING t.next_message_seq<MAX(m.seq)",
        ),
        (
            "INVALID_RUN_STATE",
            "SELECT run_id FROM runs WHERE status NOT IN "
            "('queued','running','retry_waiting','succeeded','failed','cancelled')",
        ),
        (
            "INVALID_TASK_STATE",
            "SELECT task_id FROM tasks WHERE state NOT IN "
            "('queued','leased','running','retry_waiting','succeeded','failed','cancelled')",
        ),
        (
            "TASK_RUN_CONFLICT",
            "SELECT t.task_id FROM tasks t LEFT JOIN runs r ON r.run_id=t.run_id "
            "WHERE t.kind='run' AND (r.run_id IS NULL OR r.primary_task_id IS NULL "
            "OR r.primary_task_id<>t.task_id)",
        ),
    )
    for category, query in checks:
        ids = [str(row[0]) for row in bind.execute(sa.text(query)).fetchmany(20)]
        if ids:
            # 只包含类别和内部身份，不暴露正文、快照、幂等键或连接信息。
            raise RuntimeError(f"{category}: conflicts={','.join(ids)}; 未修改既有事实")


def guard_downgrade(bind):
    if context.get_revision_argument() is None:
        raise RuntimeError("BASE_DOWNGRADE_FORBIDDEN: v2 迁移链禁止降到 base")
    checks = [
        "SELECT 1 FROM threads WHERE conversation_version=2",
        "SELECT 1 FROM runs WHERE execution_schema_version=2",
        "SELECT 1 FROM branches WHERE parent_branch_id IS NOT NULL",
        "SELECT 1 FROM runs GROUP BY user_message_id HAVING COUNT(*)>1",
        "SELECT 1 FROM session_operations",
    ]
    tables = set(sa.inspect(bind).get_table_names())
    checks += [
        f"SELECT 1 FROM {table}"
        for table in ("context_plans", "conversation_summaries")
        if table in tables
    ]
    if any(bind.execute(sa.text(query)).first() for query in checks):
        raise RuntimeError("V2_BUSINESS_FACTS: 存在 v2 事实，拒绝降级；请向前修复或恢复备份")
    if "model_profiles" in tables:
        profiles = bind.execute(sa.text("SELECT * FROM model_profiles")).mappings().all()
        for profile in profiles:
            budgets = {"mock-default": (8192, 1024), "mock-small": (2048, 256)}
            expected_budget = budgets.get(profile["profile_id"])
            tokenizer = profile["tokenizer_config"]
            generation = profile["generation_params"]
            if isinstance(tokenizer, str):
                tokenizer = json.loads(tokenizer)
            if isinstance(generation, str):
                generation = json.loads(generation)
            if (
                expected_budget is None
                or profile["version"] != 1
                or profile["provider_kind"] != "mock"
                or profile["model_name"] != "mock"
                or profile["display_name"]
                != {"mock-default": "Mock 普通上下文", "mock-small": "Mock 小上下文"}.get(
                    profile["profile_id"]
                )
                or profile["base_url"] is not None
                or profile["config_ref"] is not None
                or profile["tokenizer_kind"] != "mock"
                or profile["tokenizer_version"] != "1"
                or (profile["context_window_tokens"], profile["max_output_tokens"])
                != expected_budget
                or generation != {}
                or tokenizer != {"safety_margin_tokens": 128, "summary_max_tokens": 512}
            ):
                raise RuntimeError(
                    "CUSTOM_PROFILE_EXPORT_REQUIRED: 请先显式导出自定义 Profile，拒绝自动删除"
                )
