"""RAG 持久元数据映射；不在 ORM 中执行解析、模型或业务编排。"""

from datetime import datetime

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
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.db.models import utc_now


class EmbeddingSpaceModel(Base):
    __tablename__ = "embedding_spaces"
    __table_args__ = (
        UniqueConstraint("space_id", "dimension", name="uq_embedding_space_dimension"),
        CheckConstraint("dimension BETWEEN 1 AND 2000", name="ck_embedding_space_dimension"),
    )
    space_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    descriptor_hash: Mapped[str] = mapped_column(String(64), unique=True)
    descriptor_json: Mapped[dict] = mapped_column(JSON)
    dimension: Mapped[int] = mapped_column(Integer)


class ProfileColumns:
    profile_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_json: Mapped[dict] = mapped_column(JSON)
    config_hash: Mapped[str] = mapped_column(String(64))
    selection_status: Mapped[str] = mapped_column(String(20), default="enabled")
    security_status: Mapped[str] = mapped_column(String(20), default="allowed")
    availability_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EmbeddingProfileModel(ProfileColumns, Base):
    __tablename__ = "embedding_profiles"
    space_id: Mapped[str] = mapped_column(ForeignKey("embedding_spaces.space_id"))


class RerankProfileModel(ProfileColumns, Base):
    __tablename__ = "rerank_profiles"


class ParserProfileModel(ProfileColumns, Base):
    __tablename__ = "parser_profiles"


class RetrievalProfileModel(ProfileColumns, Base):
    __tablename__ = "retrieval_profiles"


class KnowledgeBaseModel(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_knowledge_base_owner_name"),
        UniqueConstraint("knowledge_base_id", "embedding_space_id", name="uq_kb_space"),
        UniqueConstraint("knowledge_base_id", "owner_id", name="uq_kb_owner"),
        Index(
            "uq_knowledge_base_default",
            "owner_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default"),
        ),
    )
    knowledge_base_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding_space_id: Mapped[str] = mapped_column(ForeignKey("embedding_spaces.space_id"))
    embedding_profile_id: Mapped[str] = mapped_column(String(80), default="mock-embedding")
    embedding_profile_version: Mapped[int] = mapped_column(Integer, default=1)
    scope_revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RagOperationModel(Base):
    __tablename__ = "rag_operations"
    __table_args__ = (
        UniqueConstraint("owner_id", "scope", "idempotency_key", name="uq_rag_operation_key"),
    )
    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120))
    scope: Mapped[str] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    storage_reservation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ParseJobModel(Base):
    __tablename__ = "parse_jobs"
    __table_args__ = (
        CheckConstraint("parser_kind IN ('local','mineru')", name="ck_parse_job_route"),
        CheckConstraint(
            "state IN ('queued','running','waiting','succeeded','failed','cancelled')",
            name="ck_parse_job_state",
        ),
        UniqueConstraint("parse_job_id", "document_id", name="uq_parse_job_document"),
    )
    parse_job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id"), index=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    parser_kind: Mapped[str] = mapped_column(String(20))
    routing_policy_version: Mapped[str] = mapped_column(String(40))
    parser_snapshot: Mapped[dict] = mapped_column(JSON)
    parser_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), default="queued")
    stage: Mapped[str] = mapped_column(String(40), default="preparing")
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    remote_batch_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    submission_nonce: Mapped[str | None] = mapped_column(String(36), nullable=True)
    private_state_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    remote_outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    remote_progress_json: Mapped[dict] = mapped_column(JSON, default=dict)
    poll_count: Mapped[int] = mapped_column(Integer, default=0)
    parse_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ParsedArtifactModel(Base):
    __tablename__ = "parsed_artifacts"
    __table_args__ = (
        UniqueConstraint("parse_job_id", name="uq_parsed_artifact_job"),
        UniqueConstraint("artifact_id", "parse_job_id", name="uq_artifact_job_identity"),
    )
    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parse_job_id: Mapped[str] = mapped_column(ForeignKey("parse_jobs.parse_job_id"))
    source_hash: Mapped[str] = mapped_column(String(64))
    parser_hash: Mapped[str] = mapped_column(String(64))
    protocol: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64))
    manifest_hash: Mapped[str] = mapped_column(String(64))
    unsupported_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ParsedBlockModel(Base):
    __tablename__ = "parsed_blocks"
    __table_args__ = (UniqueConstraint("artifact_id", "seq", name="uq_parsed_block_seq"),)
    block_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("parsed_artifacts.artifact_id"))
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    heading_path: Mapped[list] = mapped_column(JSON, default=list)
    locations_json: Mapped[list] = mapped_column(JSON, default=list)


class IndexBuildModel(Base):
    __tablename__ = "index_builds"
    __table_args__ = (
        UniqueConstraint("document_id", "index_batch_id", name="uq_build_document_batch"),
        UniqueConstraint(
            "index_batch_id", "document_id", "space_id", name="uq_build_document_space"
        ),
        ForeignKeyConstraint(
            ["parse_job_id", "document_id"],
            ["parse_jobs.parse_job_id", "parse_jobs.document_id"],
            name="fk_build_parse_document",
        ),
        ForeignKeyConstraint(
            ["artifact_id", "parse_job_id"],
            ["parsed_artifacts.artifact_id", "parsed_artifacts.parse_job_id"],
            name="fk_build_artifact_job",
        ),
        UniqueConstraint("index_batch_id", "knowledge_base_id", "space_id", name="uq_build_scope"),
        Index(
            "uq_build_active_candidate",
            "document_id",
            unique=True,
            postgresql_where=text("state IN ('queued','building','waiting')"),
            sqlite_where=text("state IN ('queued','building','waiting')"),
        ),
        CheckConstraint(
            "state IN ('queued','building','waiting','succeeded','failed','cancelled')",
            name="ck_build_state",
        ),
    )
    index_batch_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.knowledge_base_id"))
    space_id: Mapped[str | None] = mapped_column(
        ForeignKey("embedding_spaces.space_id"), nullable=True
    )
    parse_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("parse_jobs.parse_job_id"), nullable=True
    )
    artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("parsed_artifacts.artifact_id"), nullable=True
    )
    embedding_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    chunker_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(20), default="queued")
    stage: Mapped[str] = mapped_column(String(40), default="parse")
    provenance: Mapped[str] = mapped_column(String(30), default="new")
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RetrievalViewModel(Base):
    __tablename__ = "retrieval_views"
    __table_args__ = (
        UniqueConstraint("view_id", "knowledge_base_id", "space_id", name="uq_view_scope"),
    )
    view_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120))
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.knowledge_base_id"))
    space_id: Mapped[str] = mapped_column(ForeignKey("embedding_spaces.space_id"))
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    manifest_hash: Mapped[str] = mapped_column(String(64))
    scope_revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RetrievalViewItemModel(Base):
    __tablename__ = "retrieval_view_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["view_id", "knowledge_base_id", "space_id"],
            [
                "retrieval_views.view_id",
                "retrieval_views.knowledge_base_id",
                "retrieval_views.space_id",
            ],
            name="fk_view_item_view_scope",
        ),
        ForeignKeyConstraint(
            ["index_batch_id", "knowledge_base_id", "space_id"],
            [
                "index_builds.index_batch_id",
                "index_builds.knowledge_base_id",
                "index_builds.space_id",
            ],
            name="fk_view_item_scope",
        ),
    )
    view_id: Mapped[str] = mapped_column(ForeignKey("retrieval_views.view_id"), primary_key=True)
    index_batch_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36))
    space_id: Mapped[str] = mapped_column(String(64))


class RetrievalExecutionModel(Base):
    __tablename__ = "retrieval_executions"
    execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    view_id: Mapped[str] = mapped_column(ForeignKey("retrieval_views.view_id"))
    origin: Mapped[str] = mapped_column(String(20))
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.run_id"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    generation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    query_hash: Mapped[str] = mapped_column(String(64))
    private_query_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="queued")
    stage: Mapped[str] = mapped_column(String(40), default="preparing")
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    candidates_json: Mapped[list] = mapped_column(JSON, default=list)
    omitted_json: Mapped[list] = mapped_column(JSON, default=list)
    timings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ToolCallModel(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        UniqueConstraint("task_id", "generation", "tool_name", name="uq_tool_call_generation"),
    )
    call_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.task_id"))
    generation: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(40), default="rag.search")
    tool_version: Mapped[int] = mapped_column(Integer, default=1)
    binding_hash: Mapped[str] = mapped_column(String(64))
    execution_id: Mapped[str] = mapped_column(ForeignKey("retrieval_executions.execution_id"))
    state: Mapped[str] = mapped_column(String(20))
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)


class EvidenceBundleModel(Base):
    __tablename__ = "evidence_bundles"
    bundle_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("retrieval_executions.execution_id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id"))
    index_batch_id: Mapped[str] = mapped_column(ForeignKey("index_builds.index_batch_id"))
    anchors_json: Mapped[list] = mapped_column(JSON)
    dense_score: Mapped[float] = mapped_column()
    rerank_score: Mapped[float | None] = mapped_column(nullable=True)


class EvidenceComponentModel(Base):
    __tablename__ = "evidence_components"
    component_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bundle_id: Mapped[str] = mapped_column(ForeignKey("evidence_bundles.bundle_id"))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.chunk_id"))
    seq: Mapped[int] = mapped_column(Integer)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))


class ContextEvidenceModel(Base):
    __tablename__ = "context_evidence_ranges"
    context_evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("context_plans.context_plan_id"))
    component_id: Mapped[str] = mapped_column(ForeignKey("evidence_components.component_id"))
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    selected_hash: Mapped[str] = mapped_column(String(64))


class MessageCitationLinkModel(Base):
    __tablename__ = "message_citation_links"
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.message_id"), primary_key=True)
    context_evidence_id: Mapped[str] = mapped_column(
        ForeignKey("context_evidence_ranges.context_evidence_id"), primary_key=True
    )
    label: Mapped[str] = mapped_column(String(40))


class LegacyEvidenceRefModel(Base):
    __tablename__ = "legacy_evidence_refs"
    ref_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.message_id"), nullable=True
    )
    source_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("context_plans.context_plan_id"), nullable=True
    )
    resolved_chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("chunks.chunk_id"), nullable=True
    )
    identity_json: Mapped[dict] = mapped_column(JSON)
    availability: Mapped[str] = mapped_column(String(20))


class RagGCRecordModel(Base):
    __tablename__ = "rag_gc_records"
    record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(120))
    result: Mapped[str] = mapped_column(String(20))
    bytes_deleted: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
