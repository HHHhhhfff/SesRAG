"""PRD-003 静态迁移；禁止改变历史事实或自动调用外部服务。"""

import sqlalchemy as sa
from alembic import op

from migrations.rag_checks import guard_downgrade

revision = "0010_rag_task_and_run_protocol"
down_revision = "0009_rag_views_tools_evidence"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("index_batch_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("retrieval_execution_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True)
        )
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("retrieval_view_id", sa.String(length=36), nullable=True))
    with op.batch_alter_table("messages") as batch:
        batch.add_column(
            sa.Column("citation_schema_version", sa.Integer(), nullable=False, server_default="1")
        )
    with op.batch_alter_table("context_plans") as batch:
        batch.add_column(
            sa.Column("omitted_evidence", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.add_column(
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="2")
        )
    with op.batch_alter_table("tasks") as batch:
        batch.drop_constraint("ck_tasks_kind_target", type_="check")
        batch.create_check_constraint(
            "ck_tasks_external_wait_kind",
            "state != 'waiting_external' OR kind IN ('index_build','retrieval_diagnostic')",
        )
        batch.create_check_constraint(
            "ck_tasks_kind_target",
            "(kind = 'run' AND run_id IS NOT NULL AND document_id IS NULL "
            "AND index_batch_id IS NULL AND retrieval_execution_id IS NULL) OR "
            "(kind = 'index_document' AND document_id IS NOT NULL AND run_id IS NULL "
            "AND index_batch_id IS NULL AND retrieval_execution_id IS NULL) OR "
            "(kind = 'index_build' AND index_batch_id IS NOT NULL AND run_id IS NULL "
            "AND document_id IS NULL AND retrieval_execution_id IS NULL) OR "
            "(kind = 'retrieval_diagnostic' AND retrieval_execution_id IS NOT NULL "
            "AND run_id IS NULL AND document_id IS NULL AND index_batch_id IS NULL)",
        )
        batch.create_foreign_key(
            "fk_tasks_index_build", "index_builds", ["index_batch_id"], ["index_batch_id"]
        )
        batch.create_foreign_key(
            "fk_tasks_diagnostic",
            "retrieval_executions",
            ["retrieval_execution_id"],
            ["execution_id"],
        )
    with op.batch_alter_table("runs") as batch:
        batch.drop_constraint("ck_runs_execution_schema", type_="check")
        batch.create_check_constraint(
            "ck_runs_execution_schema", "execution_schema_version IN (1,2,3)"
        )
        batch.create_foreign_key(
            "fk_runs_retrieval_view", "retrieval_views", ["retrieval_view_id"], ["view_id"]
        )
    from migrations.rag_guards import install

    install(op.get_bind())


def downgrade():
    guard_downgrade(op.get_bind())
    from migrations.rag_guards import uninstall

    uninstall(op.get_bind())
    with op.batch_alter_table("runs") as batch:
        batch.drop_constraint("fk_runs_retrieval_view", type_="foreignkey")
        batch.drop_constraint("ck_runs_execution_schema", type_="check")
        batch.create_check_constraint(
            "ck_runs_execution_schema", "execution_schema_version IN (1,2)"
        )
        batch.drop_column("retrieval_view_id")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_constraint("fk_tasks_index_build", type_="foreignkey")
        batch.drop_constraint("fk_tasks_diagnostic", type_="foreignkey")
        batch.drop_constraint("ck_tasks_external_wait_kind", type_="check")
        batch.drop_constraint("ck_tasks_kind_target", type_="check")
        batch.create_check_constraint(
            "ck_tasks_kind_target",
            "(kind='run' AND run_id IS NOT NULL AND document_id IS NULL) OR "
            "(kind='index_document' AND document_id IS NOT NULL AND run_id IS NULL)",
        )
        for name in (
            "index_batch_id",
            "retrieval_execution_id",
            "failure_count",
            "cancel_requested_at",
        ):
            batch.drop_column(name)
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("citation_schema_version")
    with op.batch_alter_table("context_plans") as batch:
        batch.drop_column("schema_version")
        batch.drop_column("omitted_evidence")
