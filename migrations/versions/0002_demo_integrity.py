"""新增幂等、任务关联和最终回答约束，补齐安全逻辑来源。"""

import sqlalchemy as sa
from alembic import op

revision = "0002_demo_integrity"
down_revision = "0001_initial_demo"
branch_labels = None
depends_on = None

TASK_TARGET = (
    "(kind = 'run' AND run_id IS NOT NULL AND document_id IS NULL) OR "
    "(kind = 'index_document' AND document_id IS NOT NULL AND run_id IS NULL)"
)


def upgrade() -> None:
    bind = op.get_bind()
    # 并发业务写入必须与诊断、建约束处于同一互斥区，防止检查后出现新冲突。
    if bind.dialect.name == "postgresql":
        op.execute("LOCK TABLE messages, tasks, documents IN ACCESS EXCLUSIVE MODE")
    for code, query in (
        (
            "MESSAGE_IDEMPOTENCY_CONFLICT",
            "SELECT 1 FROM messages WHERE idempotency_key IS NOT NULL "
            "GROUP BY thread_id,idempotency_key HAVING COUNT(*) > 1",
        ),
        (
            "ASSISTANT_RUN_CONFLICT",
            "SELECT 1 FROM messages WHERE role='assistant' AND run_id IS NOT NULL "
            "GROUP BY run_id HAVING COUNT(*) > 1",
        ),
        ("TASK_TARGET_CONFLICT", f"SELECT 1 FROM tasks WHERE NOT ({TASK_TARGET})"),
        (
            "MESSAGE_SOURCE_CONFLICT",
            "SELECT 1 FROM messages WHERE role NOT IN ('user','assistant')",
        ),
    ):
        if bind.execute(sa.text(query)).first():
            # 只报告冲突类别，不输出消息正文、幂等键或凭据。
            raise RuntimeError(f"{code}: 既有事实冲突，修复后再升级；未自动删除或合并")
    inspector = sa.inspect(bind)
    if "source" not in {c["name"] for c in inspector.get_columns("messages")}:
        op.add_column("messages", sa.Column("source", sa.String(40), nullable=True))
    op.execute(
        "UPDATE messages SET source=CASE WHEN role='assistant' "
        "THEN 'assistant_generation' ELSE 'user_input' END WHERE source IS NULL"
    )
    with op.batch_alter_table("messages") as batch:
        batch.alter_column("source", existing_type=sa.String(40), nullable=False)
    if "source" not in {c["name"] for c in inspector.get_columns("documents")}:
        op.add_column("documents", sa.Column("source", sa.String(40), nullable=True))
    op.execute("UPDATE documents SET source='local_upload' WHERE source IS NULL")
    with op.batch_alter_table("documents") as batch:
        batch.alter_column("source", existing_type=sa.String(40), nullable=False)
    with op.batch_alter_table("messages") as batch:
        batch.create_unique_constraint(
            "uq_messages_thread_idempotency", ["thread_id", "idempotency_key"]
        )
    op.create_index(
        "uq_messages_assistant_run",
        "messages",
        ["run_id"],
        unique=True,
        postgresql_where=sa.text("role='assistant'"),
        sqlite_where=sa.text("role='assistant'"),
    )
    with op.batch_alter_table("tasks") as batch:
        batch.create_check_constraint("ck_tasks_kind_target", TASK_TARGET)


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.drop_constraint("ck_tasks_kind_target", type_="check")
    op.drop_index("uq_messages_assistant_run", table_name="messages")
    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint("uq_messages_thread_idempotency", type_="unique")
        batch.alter_column("source", existing_type=sa.String(40), nullable=True)
    with op.batch_alter_table("documents") as batch:
        batch.alter_column("source", existing_type=sa.String(40), nullable=True)
    # 降级保留来源事实，允许旧代码省略附加列；再次升级只补齐空来源。
