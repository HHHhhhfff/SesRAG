"""持久 Branch、会话代际和可复用 Run 输入。"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from migrations.v2_session_checks import guard_downgrade, preflight

revision = "0004_v2_session_branches"
down_revision = "0003_chunk_locations"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    preflight(bind)
    with op.batch_alter_table("threads") as batch:
        batch.add_column(
            sa.Column("conversation_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.create_check_constraint("ck_threads_version", "conversation_version IN (1,2)")
    op.create_table(
        "branches",
        sa.Column("branch_id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.thread_id"), nullable=False),
        sa.Column("parent_branch_id", sa.String(36), sa.ForeignKey("branches.branch_id")),
        sa.Column(
            "fork_message_id",
            sa.String(36),
            sa.ForeignKey("messages.message_id", name="fk_branches_fork"),
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column(
            "head_message_id",
            sa.String(36),
            sa.ForeignKey("messages.message_id", name="fk_branches_head"),
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(parent_branch_id IS NULL AND fork_message_id IS NULL) OR "
            "(parent_branch_id IS NOT NULL AND fork_message_id IS NOT NULL)",
            name="ck_branches_fork_pair",
        ),
        sa.CheckConstraint("version>=0", name="ck_branches_version"),
    )
    op.create_index("ix_branches_thread_id", "branches", ["thread_id"])
    op.create_index(
        "uq_branches_default",
        "branches",
        ["thread_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        sqlite_where=sa.text("is_default"),
    )
    op.add_column("messages", sa.Column("branch_id", sa.String(36), nullable=True))
    for column in (
        sa.Column("branch_id", sa.String(36)),
        sa.Column("parent_run_id", sa.String(36)),
        sa.Column("operation_kind", sa.String(30), server_default="initial"),
        sa.Column("execution_schema_version", sa.Integer(), server_default="1"),
    ):
        op.add_column("runs", column)
    for thread in (
        bind.execute(sa.text("SELECT thread_id,created_at,updated_at FROM threads"))
        .mappings()
        .all()
    ):
        bid = str(uuid4())
        head = bind.execute(
            sa.text(
                "SELECT message_id,seq FROM messages WHERE thread_id=:tid ORDER BY seq DESC LIMIT 1"
            ),
            {"tid": thread["thread_id"]},
        ).first()
        bind.execute(
            sa.text(
                "INSERT INTO branches (branch_id,thread_id,name,is_default,head_message_id,"
                "version,created_at,updated_at) VALUES "
                "(:bid,:tid,'默认分支',:default,:head,:version,:created,:updated)"
            ),
            {
                "bid": bid,
                "tid": thread["thread_id"],
                "default": True,
                "head": head[0] if head else None,
                "version": head[1] if head else 0,
                "created": thread["created_at"],
                "updated": thread["updated_at"],
            },
        )
        for table in ("messages", "runs"):
            bind.execute(
                sa.text(f"UPDATE {table} SET branch_id=:bid WHERE thread_id=:tid"),
                {"bid": bid, "tid": thread["thread_id"]},
            )
    with op.batch_alter_table("messages") as batch:
        batch.alter_column("branch_id", existing_type=sa.String(36), nullable=False)
        batch.create_foreign_key("fk_messages_branch", "branches", ["branch_id"], ["branch_id"])
        batch.create_index("ix_messages_branch_id", ["branch_id"])
    # 0001 的匿名 UNIQUE 通过命名约定识别；不修改已发布迁移。
    input_unique = next(
        c["name"] or "uq_runs_user_message_id"
        for c in sa.inspect(bind).get_unique_constraints("runs")
        if c["column_names"] == ["user_message_id"]
    )
    with op.batch_alter_table(
        "runs", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch:
        batch.drop_constraint(input_unique, type_="unique")
        batch.create_foreign_key(
            "fk_runs_user_message", "messages", ["user_message_id"], ["message_id"]
        )
        batch.create_foreign_key("fk_runs_branch", "branches", ["branch_id"], ["branch_id"])
        batch.create_foreign_key("fk_runs_parent", "runs", ["parent_run_id"], ["run_id"])
        batch.create_index("ix_runs_user_message_id", ["user_message_id"])
        batch.create_index("ix_runs_branch_id", ["branch_id"])
        for name, typ in (
            ("branch_id", sa.String(36)),
            ("operation_kind", sa.String(30)),
            ("execution_schema_version", sa.Integer()),
        ):
            batch.alter_column(name, existing_type=typ, nullable=False)
    op.create_table(
        "session_operations",
        sa.Column("operation_id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.thread_id"), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        *[
            sa.Column(f"result_{name}_id", sa.String(36), sa.ForeignKey(f"{table}.{name}_id"))
            for name, table in (
                ("branch", "branches"),
                ("message", "messages"),
                ("run", "runs"),
                ("task", "tasks"),
            )
        ],
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("thread_id", "idempotency_key", name="uq_session_operations_key"),
    )
    op.create_index("ix_session_operations_thread_id", "session_operations", ["thread_id"])


def downgrade():
    guard_downgrade(op.get_bind())
    op.drop_table("session_operations")
    with op.batch_alter_table("runs") as batch:
        for name in ("fk_runs_user_message", "fk_runs_branch", "fk_runs_parent"):
            batch.drop_constraint(name, type_="foreignkey")
        batch.drop_index("ix_runs_user_message_id")
        batch.drop_index("ix_runs_branch_id")
        batch.create_unique_constraint("uq_runs_user_message_id", ["user_message_id"])
        for name in ("branch_id", "parent_run_id", "operation_kind", "execution_schema_version"):
            batch.drop_column(name)
    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint("fk_messages_branch", type_="foreignkey")
        batch.drop_index("ix_messages_branch_id")
        batch.drop_column("branch_id")
    op.drop_table("branches")
    with op.batch_alter_table("threads") as batch:
        batch.drop_constraint("ck_threads_version", type_="check")
        batch.drop_column("conversation_version")
