"""单 Branch 活动执行和单 Run Task 数据库屏障。"""

import sqlalchemy as sa
from alembic import op

from migrations.v2_session_checks import guard_downgrade

revision = "0006_v2_run_guards"
down_revision = "0005_v2_profiles_context"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("LOCK TABLE runs,tasks IN ACCESS EXCLUSIVE MODE"))
    # 单独从 0005 升级也必须显式诊断，不依赖唯一异常泄漏。
    for code, sql in (
        (
            "ACTIVE_BRANCH_CONFLICT",
            "SELECT branch_id FROM runs WHERE "
            "status IN ('queued','running','retry_waiting','cancelling') "
            "GROUP BY branch_id HAVING COUNT(*)>1",
        ),
        (
            "RUN_TASK_CONFLICT",
            "SELECT run_id FROM tasks WHERE kind='run' GROUP BY run_id HAVING COUNT(*)>1",
        ),
        (
            "INVALID_RUN_STATE",
            "SELECT run_id FROM runs WHERE status NOT IN "
            "('queued','running','retry_waiting','cancelling','succeeded','failed','cancelled')",
        ),
    ):
        if bind.execute(sa.text(sql)).first():
            raise RuntimeError(f"{code}: 既有事实冲突，未自动取消或删除")
    with op.batch_alter_table("runs") as batch:
        batch.create_check_constraint(
            "ck_runs_status",
            "status IN ('queued','running','retry_waiting','cancelling',"
            "'succeeded','failed','cancelled')",
        )
        batch.create_check_constraint(
            "ck_runs_execution_schema", "execution_schema_version IN (1,2)"
        )
        batch.create_check_constraint(
            "ck_runs_operation_kind",
            "operation_kind IN ('initial','user_retry','regenerate','branch_continue')",
        )
    op.create_index(
        "uq_runs_branch_active",
        "runs",
        ["branch_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running','retry_waiting','cancelling')"),
        sqlite_where=sa.text("status IN ('queued','running','retry_waiting','cancelling')"),
    )
    op.create_index(
        "uq_tasks_run",
        "tasks",
        ["run_id"],
        unique=True,
        postgresql_where=sa.text("kind='run'"),
        sqlite_where=sa.text("kind='run'"),
    )


def downgrade():
    # 在最前面的反向 revision 守门，失败时不先拆除任何保护。
    guard_downgrade(op.get_bind())
    op.drop_index("uq_tasks_run", table_name="tasks")
    op.drop_index("uq_runs_branch_active", table_name="runs")
    with op.batch_alter_table("runs") as batch:
        for name in ("ck_runs_status", "ck_runs_execution_schema", "ck_runs_operation_kind"):
            batch.drop_constraint(name, type_="check")
