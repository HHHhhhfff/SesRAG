"""PRD-003 静态迁移；禁止改变历史事实或自动调用外部服务。"""

import sqlalchemy as sa
from alembic import op

from migrations.rag_checks import guard_downgrade

revision = "0008_rag_builds_and_vectors"
down_revision = "0007_rag_catalog_and_profiles"
branch_labels = None
depends_on = None


def upgrade():
    from migrations.rag_checks import prepare_legacy_documents

    prepare_legacy_documents(op.get_bind())
    op.create_table(
        "parse_jobs",
        sa.Column("parse_job_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_kind", sa.String(length=20), nullable=False),
        sa.Column("routing_policy_version", sa.String(length=40), nullable=False),
        sa.Column("parser_snapshot", sa.JSON(), nullable=False),
        sa.Column("parser_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("remote_batch_id", sa.String(length=200), nullable=True),
        sa.Column("submission_nonce", sa.String(length=36), nullable=True),
        sa.Column("private_state_key", sa.String(length=120), nullable=True),
        sa.Column("remote_outcome", sa.String(length=40), nullable=True),
        sa.Column("remote_progress_json", sa.JSON(), nullable=False),
        sa.Column("poll_count", sa.Integer(), nullable=False),
        sa.Column("parse_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("parse_job_id", "document_id", name="uq_parse_job_document"),
        sa.CheckConstraint("parser_kind IN ('local','mineru')", name="ck_parse_job_route"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name=None),
        sa.CheckConstraint(
            "state IN ('queued','running','waiting','succeeded','failed','cancelled')",
            name="ck_parse_job_state",
        ),
    )
    op.create_index("ix_parse_jobs_document_id", "parse_jobs", ["document_id"], unique=False)
    op.create_table(
        "parsed_artifacts",
        sa.Column("artifact_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("parse_job_id", sa.String(length=36), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_hash", sa.String(length=64), nullable=False),
        sa.Column("protocol", sa.String(length=80), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("unsupported_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("parse_job_id", name="uq_parsed_artifact_job"),
        sa.ForeignKeyConstraint(["parse_job_id"], ["parse_jobs.parse_job_id"], name=None),
    )
    op.create_table(
        "parsed_blocks",
        sa.Column("block_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("artifact_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.JSON(), nullable=False),
        sa.Column("locations_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["parsed_artifacts.artifact_id"], name=None),
        sa.UniqueConstraint("artifact_id", "seq", name="uq_parsed_block_seq"),
    )
    op.create_table(
        "index_builds",
        sa.Column("index_batch_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=64), nullable=True),
        sa.Column("parse_job_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("embedding_snapshot", sa.JSON(), nullable=False),
        sa.Column("chunker_snapshot", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("provenance", sa.String(length=30), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name=None),
        sa.CheckConstraint(
            "state IN ('queued','building','waiting','succeeded','failed','cancelled')",
            name="ck_build_state",
        ),
        sa.UniqueConstraint(
            "index_batch_id", "knowledge_base_id", "space_id", name="uq_build_scope"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"], ["knowledge_bases.knowledge_base_id"], name=None
        ),
        sa.UniqueConstraint("document_id", "index_batch_id", name="uq_build_document_batch"),
        sa.ForeignKeyConstraint(["space_id"], ["embedding_spaces.space_id"], name=None),
        sa.ForeignKeyConstraint(["artifact_id"], ["parsed_artifacts.artifact_id"], name=None),
        sa.ForeignKeyConstraint(["parse_job_id"], ["parse_jobs.parse_job_id"], name=None),
    )
    op.create_index("ix_index_builds_document_id", "index_builds", ["document_id"], unique=False)
    op.create_index(
        "uq_build_active_candidate",
        "index_builds",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('queued','building','waiting')"),
        sqlite_where=sa.text("state IN ('queued','building','waiting')"),
    )
    with op.batch_alter_table("chunks") as batch:
        batch.add_column(sa.Column("space_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("dimension", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("content_hash", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("block_segments_json", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.add_column(
            sa.Column("legacy_unverified", sa.Boolean(), nullable=False, server_default="false")
        )
        batch.create_foreign_key(
            "fk_chunks_space_dimension",
            "embedding_spaces",
            ["space_id", "dimension"],
            ["space_id", "dimension"],
        )
        batch.create_check_constraint(
            "ck_chunks_dimension", "dimension IS NULL OR dimension BETWEEN 1 AND 2000"
        )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector USING embedding::vector")
        op.create_check_constraint(
            "ck_chunks_vector_dims",
            "chunks",
            "embedding IS NULL OR dimension IS NULL OR vector_dims(embedding)=dimension",
        )
    from migrations.rag_checks import backfill_legacy_builds

    backfill_legacy_builds(op.get_bind())
    # 指针与文档共同构成身份，数据库拒绝误指向另一文档的批次。
    with op.batch_alter_table("documents") as batch:
        for column, name in (
            ("active_index_batch_id", "fk_document_active_batch"),
            ("latest_index_batch_id", "fk_document_latest_batch"),
        ):
            batch.create_foreign_key(
                name, "index_builds", ["document_id", column], ["document_id", "index_batch_id"]
            )
    with op.batch_alter_table("parsed_artifacts") as batch:
        batch.create_unique_constraint("uq_artifact_job_identity", ["artifact_id", "parse_job_id"])
    with op.batch_alter_table("index_builds") as batch:
        batch.create_unique_constraint(
            "uq_build_document_space", ["index_batch_id", "document_id", "space_id"]
        )
        batch.create_foreign_key(
            "fk_build_parse_document",
            "parse_jobs",
            ["parse_job_id", "document_id"],
            ["parse_job_id", "document_id"],
        )
        batch.create_foreign_key(
            "fk_build_artifact_job",
            "parsed_artifacts",
            ["artifact_id", "parse_job_id"],
            ["artifact_id", "parse_job_id"],
        )
    with op.batch_alter_table("chunks") as batch:
        batch.create_foreign_key(
            "fk_chunks_build_document_space",
            "index_builds",
            ["index_batch_id", "document_id", "space_id"],
            ["index_batch_id", "document_id", "space_id"],
        )


def downgrade():
    guard_downgrade(op.get_bind())
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_document_active_batch", type_="foreignkey")
        batch.drop_constraint("fk_document_latest_batch", type_="foreignkey")
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_chunks_vector_dims", "chunks", type_="check")
        op.execute(
            "ALTER TABLE chunks ALTER COLUMN embedding "
            "TYPE vector(384) USING embedding::vector(384)"
        )
    with op.batch_alter_table("chunks") as batch:
        batch.drop_constraint("fk_chunks_build_document_space", type_="foreignkey")
        batch.drop_constraint("fk_chunks_space_dimension", type_="foreignkey")
        batch.drop_constraint("ck_chunks_dimension", type_="check")
        for name in (
            "space_id",
            "dimension",
            "content_hash",
            "block_segments_json",
            "legacy_unverified",
        ):
            batch.drop_column(name)
    for name in ("index_builds", "parsed_blocks", "parsed_artifacts", "parse_jobs"):
        op.drop_table(name)
