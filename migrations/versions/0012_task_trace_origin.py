"""为 Task 保存不可变、可缺失的追踪来源。"""

import sqlalchemy as sa
from alembic import context, op

revision = "0012_task_trace_origin"
down_revision = "0011_rag_source_integrity"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '1s'")
        op.execute("SET LOCAL statement_timeout = '30s'")
    op.add_column(
        "tasks", sa.Column("trace_origin_json", sa.JSON(none_as_null=True), nullable=True)
    )
    if bind.dialect.name == "postgresql":
        op.execute("""
            CREATE FUNCTION task_trace_origin_immutable() RETURNS trigger AS $$
            BEGIN
                IF OLD.trace_origin_json::jsonb IS DISTINCT FROM NEW.trace_origin_json::jsonb THEN
                    RAISE EXCEPTION 'TASK_TRACE_ORIGIN_IMMUTABLE';
                END IF;
                RETURN NEW;
            END $$ LANGUAGE plpgsql
        """)
        op.execute("""
            CREATE TRIGGER task_trace_origin_immutable BEFORE UPDATE ON tasks
            FOR EACH ROW EXECUTE FUNCTION task_trace_origin_immutable()
        """)
    elif bind.dialect.name == "sqlite":
        op.execute("""
            CREATE TRIGGER task_trace_origin_immutable BEFORE UPDATE OF trace_origin_json ON tasks
            WHEN OLD.trace_origin_json IS NOT NEW.trace_origin_json
            BEGIN SELECT RAISE(ABORT, 'TASK_TRACE_ORIGIN_IMMUTABLE'); END
        """)


def downgrade():
    if context.get_x_argument(as_dictionary=True).get("allow_observability_loss") != "true":
        raise RuntimeError("OBSERVABILITY_LOSS_CONFIRMATION_REQUIRED")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER task_trace_origin_immutable ON tasks")
        op.execute("DROP FUNCTION task_trace_origin_immutable()")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER task_trace_origin_immutable")
    op.drop_column("tasks", "trace_origin_json")
