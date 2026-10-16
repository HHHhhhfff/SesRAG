"""固定 SesRAG Demo 首版 Schema；不依赖运行时 ORM。"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001_initial_demo"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "threads",
        sa.Column("thread_id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(120), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("next_message_seq", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "messages",
        sa.Column("message_id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.thread_id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("run_id", sa.String(36)),
        sa.Column("citations_json", sa.JSON()),
        sa.Column("idempotency_key", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("thread_id", "seq", name="uq_messages_thread_seq"),
    )
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.thread_id"), nullable=False),
        sa.Column("user_message_id", sa.String(36), nullable=False, unique=True),
        sa.Column("assistant_message_id", sa.String(36)),
        sa.Column("primary_task_id", sa.String(36)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("next_event_seq", sa.Integer(), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.run_id")),
        sa.Column("document_id", sa.String(36)),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("worker_id", sa.String(120)),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("progress_json", sa.JSON(), nullable=False),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("last_error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "run_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.run_id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),
    )
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(120), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("extension", sa.String(20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("active_index_batch_id", sa.String(36)),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    embedding_type = Vector(384) if op.get_bind().dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id", sa.String(36), sa.ForeignKey("documents.document_id"), nullable=False
        ),
        sa.Column("index_batch_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("embedding", embedding_type),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "index_batch_id", "seq", name="uq_chunks_batch_seq"),
    )
    for table, columns in (
        ("threads", ("owner_id",)),
        ("messages", ("thread_id", "run_id", "idempotency_key")),
        ("runs", ("thread_id", "status")),
        (
            "tasks",
            (
                "kind",
                "run_id",
                "document_id",
                "state",
                "available_at",
                "deadline_at",
                "lease_expires_at",
            ),
        ),
        ("run_events", ("run_id",)),
        ("documents", ("owner_id", "content_hash", "status")),
        ("chunks", ("document_id", "index_batch_id")),
    ):
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    tables = ("chunks", "run_events", "tasks", "runs", "messages", "documents", "threads")
    if op.get_bind().dialect.name == "postgresql":
        # 同一事务先锁齐所有业务表；判空后不允许 INSERT 越过检查再被 DROP 丢弃。
        for table in tables:
            op.execute(sa.text(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE"))
    # 初始卸载只适用于空库；已有用户事实必须通过备份/运维流程处理。
    for table in tables:
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("NONEMPTY_DATABASE: 拒绝初始降级删除业务事实")
    for table in tables:
        op.drop_table(table)
