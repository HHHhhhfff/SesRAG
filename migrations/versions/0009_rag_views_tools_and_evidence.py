"""PRD-003 静态迁移；禁止改变历史事实或自动调用外部服务。"""

import sqlalchemy as sa
from alembic import op

from migrations.rag_checks import guard_downgrade

revision = "0009_rag_views_tools_evidence"
down_revision = "0008_rag_builds_and_vectors"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "retrieval_views",
        sa.Column("view_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("owner_id", sa.String(length=120), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=64), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("scope_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["embedding_spaces.space_id"], name=None),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"], ["knowledge_bases.knowledge_base_id"], name=None
        ),
    )
    op.create_table(
        "retrieval_view_items",
        sa.Column("view_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("index_batch_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["view_id"], ["retrieval_views.view_id"], name=None),
        sa.ForeignKeyConstraint(
            ["index_batch_id", "knowledge_base_id", "space_id"],
            [
                "index_builds.index_batch_id",
                "index_builds.knowledge_base_id",
                "index_builds.space_id",
            ],
            name="fk_view_item_scope",
        ),
    )
    op.create_table(
        "retrieval_executions",
        sa.Column("execution_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("view_id", sa.String(length=36), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("generation", sa.Integer(), nullable=True),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("private_query_key", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=True),
        sa.Column("candidates_json", sa.JSON(), nullable=False),
        sa.Column("omitted_json", sa.JSON(), nullable=False),
        sa.Column("timings_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["view_id"], ["retrieval_views.view_id"], name=None),
        sa.ForeignKeyConstraint(["run_id"], ["runs.run_id"], name=None),
    )
    op.create_table(
        "tool_calls",
        sa.Column("call_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=40), nullable=False),
        sa.Column("tool_version", sa.Integer(), nullable=False),
        sa.Column("binding_hash", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["execution_id"], ["retrieval_executions.execution_id"], name=None),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.task_id"], name=None),
        sa.ForeignKeyConstraint(["run_id"], ["runs.run_id"], name=None),
        sa.UniqueConstraint("task_id", "generation", "tool_name", name="uq_tool_call_generation"),
    )
    op.create_table(
        "evidence_bundles",
        sa.Column("bundle_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("index_batch_id", sa.String(length=36), nullable=False),
        sa.Column("anchors_json", sa.JSON(), nullable=False),
        sa.Column("dense_score", sa.Double(), nullable=False),
        sa.Column("rerank_score", sa.Double(), nullable=True),
        sa.ForeignKeyConstraint(["execution_id"], ["retrieval_executions.execution_id"], name=None),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name=None),
        sa.ForeignKeyConstraint(["index_batch_id"], ["index_builds.index_batch_id"], name=None),
    )
    op.create_table(
        "evidence_components",
        sa.Column("component_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("bundle_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.chunk_id"], name=None),
        sa.ForeignKeyConstraint(["bundle_id"], ["evidence_bundles.bundle_id"], name=None),
    )
    op.create_table(
        "context_evidence_ranges",
        sa.Column("context_evidence_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("component_id", sa.String(length=36), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("selected_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["context_plans.context_plan_id"], name=None),
        sa.ForeignKeyConstraint(["component_id"], ["evidence_components.component_id"], name=None),
    )
    op.create_table(
        "message_citation_links",
        sa.Column("message_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("context_evidence_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.message_id"], name=None),
        sa.ForeignKeyConstraint(
            ["context_evidence_id"], ["context_evidence_ranges.context_evidence_id"], name=None
        ),
    )
    op.create_table(
        "legacy_evidence_refs",
        sa.Column("ref_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
        sa.Column("source_plan_id", sa.String(length=36), nullable=True),
        sa.Column("resolved_chunk_id", sa.String(length=36), nullable=True),
        sa.Column("identity_json", sa.JSON(), nullable=False),
        sa.Column("availability", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.message_id"], name=None),
        sa.ForeignKeyConstraint(["resolved_chunk_id"], ["chunks.chunk_id"], name=None),
        sa.ForeignKeyConstraint(["source_plan_id"], ["context_plans.context_plan_id"], name=None),
    )
    op.create_table(
        "rag_gc_records",
        sa.Column("record_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("resource_id", sa.String(length=120), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("bytes_deleted", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    from migrations.rag_checks import protect_legacy_evidence

    protect_legacy_evidence(op.get_bind())
    with op.batch_alter_table("retrieval_views") as batch:
        batch.create_unique_constraint(
            "uq_view_scope", ["view_id", "knowledge_base_id", "space_id"]
        )
    with op.batch_alter_table("retrieval_view_items") as batch:
        batch.create_foreign_key(
            "fk_view_item_view_scope",
            "retrieval_views",
            ["view_id", "knowledge_base_id", "space_id"],
            ["view_id", "knowledge_base_id", "space_id"],
        )


def downgrade():
    guard_downgrade(op.get_bind())
    for name in (
        "rag_gc_records",
        "legacy_evidence_refs",
        "message_citation_links",
        "context_evidence_ranges",
        "evidence_components",
        "evidence_bundles",
        "tool_calls",
        "retrieval_executions",
        "retrieval_view_items",
        "retrieval_views",
    ):
        op.drop_table(name)
