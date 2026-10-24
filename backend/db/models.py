from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - 依赖由生产镜像安装
    Vector = None  # type: ignore[assignment,misc]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EmbeddingType(TypeDecorator[list[float]]):
    """PostgreSQL 使用 pgvector，SQLite 测试使用 JSON。"""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(384))
        return dialect.type_descriptor(JSON())


class ThreadModel(Base):
    __tablename__ = "threads"
    __table_args__ = (CheckConstraint("conversation_version IN (1,2)", name="ck_threads_version"),)

    thread_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(200), default="新会话")
    next_message_seq: Mapped[int] = mapped_column(Integer, default=0)
    conversation_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class BranchModel(Base):
    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint(
            "(parent_branch_id IS NULL AND fork_message_id IS NULL) OR "
            "(parent_branch_id IS NOT NULL AND fork_message_id IS NOT NULL)",
            name="ck_branches_fork_pair",
        ),
        CheckConstraint("version >= 0", name="ck_branches_version"),
        Index(
            "uq_branches_default",
            "thread_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default"),
        ),
    )
    branch_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.thread_id"), index=True)
    parent_branch_id: Mapped[str | None] = mapped_column(
        ForeignKey("branches.branch_id"), nullable=True
    )
    fork_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.message_id", use_alter=True, name="fk_branches_fork"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(80))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    head_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.message_id", use_alter=True, name="fk_branches_head"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SessionOperationModel(Base):
    __tablename__ = "session_operations"
    __table_args__ = (
        UniqueConstraint("thread_id", "idempotency_key", name="uq_session_operations_key"),
    )
    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.thread_id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    request_hash: Mapped[str] = mapped_column(String(64))
    result_branch_id: Mapped[str | None] = mapped_column(
        ForeignKey("branches.branch_id"), nullable=True
    )
    result_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.message_id"), nullable=True
    )
    result_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.run_id"), nullable=True)
    result_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.task_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ModelProfileModel(Base):
    __tablename__ = "model_profiles"
    __table_args__ = (
        CheckConstraint(
            "version > 0 AND context_window_tokens > 0 AND max_output_tokens > 0",
            name="ck_model_profiles_budgets",
        ),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_model_profiles_status"),
        CheckConstraint(
            "NOT is_default OR status='enabled'", name="ck_model_profiles_default_enabled"
        ),
        Index(
            "uq_model_profiles_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default"),
        ),
    )
    profile_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    provider_kind: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(200))
    generation_params: Mapped[dict] = mapped_column(JSON, default=dict)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    context_window_tokens: Mapped[int] = mapped_column(Integer)
    max_output_tokens: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    is_default: Mapped[bool] = mapped_column(Boolean)
    tokenizer_kind: Mapped[str] = mapped_column(String(40))
    tokenizer_version: Mapped[str] = mapped_column(String(40))
    tokenizer_config: Mapped[dict] = mapped_column(JSON, default=dict)
    config_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ContextPlanModel(Base):
    __tablename__ = "context_plans"
    __table_args__ = (
        UniqueConstraint("task_id", "generation", name="uq_context_plans_task_generation"),
    )
    context_plan_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.task_id"))
    generation: Mapped[int] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.thread_id"))
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.branch_id"))
    anchor_message_id: Mapped[str] = mapped_column(ForeignKey("messages.message_id"))
    selected_message_ids: Mapped[list] = mapped_column(JSON, default=list)
    omitted_messages: Mapped[list] = mapped_column(JSON, default=list)
    omitted_ranges: Mapped[list] = mapped_column(JSON, default=list)
    summary_ids: Mapped[list] = mapped_column(JSON, default=list)
    selected_evidence: Mapped[list] = mapped_column(JSON, default=list)
    trim_policy_version: Mapped[str] = mapped_column(String(40))
    counter_version: Mapped[str] = mapped_column(String(40))
    estimated_input_tokens: Mapped[int] = mapped_column(Integer)
    reserved_output_tokens: Mapped[int] = mapped_column(Integer)
    safety_margin_tokens: Mapped[int] = mapped_column(Integer)
    context_window_tokens: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationSummaryModel(Base):
    __tablename__ = "conversation_summaries"
    summary_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.thread_id"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.branch_id"), index=True)
    covered_message_ids: Mapped[list] = mapped_column(JSON)
    from_seq: Mapped[int] = mapped_column(Integer)
    to_seq: Mapped[int] = mapped_column(Integer)
    source_hash: Mapped[str] = mapped_column(String(64))
    source_segments: Mapped[list] = mapped_column(JSON)
    summary_text: Mapped[str] = mapped_column(Text)
    summary_policy_version: Mapped[str] = mapped_column(String(40))
    source_run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("thread_id", "seq", name="uq_messages_thread_seq"),
        UniqueConstraint("thread_id", "idempotency_key", name="uq_messages_thread_idempotency"),
        # user 和 assistant 均关联 Run，只约束最终 assistant 的唯一性。
        Index(
            "uq_messages_assistant_run",
            "run_id",
            unique=True,
            postgresql_where=text("role = 'assistant'"),
            sqlite_where=text("role = 'assistant'"),
        ),
    )

    message_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.thread_id"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.branch_id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(40), default="user_input")
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    citations_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RunModel(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','retry_waiting','cancelling',"
            "'succeeded','failed','cancelled')",
            name="ck_runs_status",
        ),
        CheckConstraint("execution_schema_version IN (1,2)", name="ck_runs_execution_schema"),
        CheckConstraint(
            "operation_kind IN ('initial','user_retry','regenerate','branch_continue')",
            name="ck_runs_operation_kind",
        ),
        ForeignKeyConstraint(
            ["model_profile_id", "model_profile_version"],
            ["model_profiles.profile_id", "model_profiles.version"],
            name="fk_runs_model_profile",
        ),
        Index(
            "uq_runs_branch_active",
            "branch_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running','retry_waiting','cancelling')"),
            sqlite_where=text("status IN ('queued','running','retry_waiting','cancelling')"),
        ),
    )

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.thread_id"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.branch_id"), index=True)
    user_message_id: Mapped[str] = mapped_column(ForeignKey("messages.message_id"), index=True)
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.run_id"), nullable=True)
    operation_kind: Mapped[str] = mapped_column(
        String(30), default="initial", server_default="initial"
    )
    execution_schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    context_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("context_plans.context_plan_id", use_alter=True, name="fk_runs_context_plan"),
        nullable=True,
    )
    model_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    model_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assistant_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    primary_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    next_event_seq: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index(
            "uq_tasks_run",
            "run_id",
            unique=True,
            postgresql_where=text("kind='run'"),
            sqlite_where=text("kind='run'"),
        ),
        CheckConstraint(
            "(kind = 'run' AND run_id IS NOT NULL AND document_id IS NULL) OR "
            "(kind = 'index_document' AND document_id IS NOT NULL AND run_id IS NULL)",
            name="ck_tasks_kind_target",
        ),
    )

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.run_id"), nullable=True, index=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(30), index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    progress_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RunEventModel(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    type: Mapped[str] = mapped_column(String(80))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DocumentModel(Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(40), default="local_upload")
    extension: Mapped[str] = mapped_column(String(20))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    active_index_batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ChunkModel(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "index_batch_id", "seq", name="uq_chunks_batch_seq"),
    )

    chunk_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id"), index=True)
    index_batch_id: Mapped[str] = mapped_column(String(36), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType(), nullable=True)
    locations_json: Mapped[list[dict]] = mapped_column(JSON, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
