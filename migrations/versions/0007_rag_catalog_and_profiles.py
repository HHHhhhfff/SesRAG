"""PRD-003 静态迁移；禁止改变历史事实或自动调用外部服务。"""

import sqlalchemy as sa
from alembic import op

from migrations.rag_checks import guard_downgrade

revision = "0007_rag_catalog_and_profiles"
down_revision = "0006_v2_run_guards"
branch_labels = None
depends_on = None


def upgrade():
    from migrations.rag_checks import drain_legacy_docx

    drain_legacy_docx(op.get_bind())
    op.create_table(
        "embedding_spaces",
        sa.Column("space_id", sa.String(length=64), nullable=False, primary_key=True),
        sa.Column("descriptor_hash", sa.String(length=64), nullable=False),
        sa.Column("descriptor_json", sa.JSON(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.UniqueConstraint("space_id", "dimension", name="uq_embedding_space_dimension"),
        sa.CheckConstraint("dimension BETWEEN 1 AND 2000", name="ck_embedding_space_dimension"),
        sa.UniqueConstraint("descriptor_hash", name=None),
    )
    op.create_table(
        "embedding_profiles",
        sa.Column("space_id", sa.String(length=64), nullable=False),
        sa.Column("profile_id", sa.String(length=80), nullable=False, primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("selection_status", sa.String(length=20), nullable=False),
        sa.Column("security_status", sa.String(length=20), nullable=False),
        sa.Column("availability_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["embedding_spaces.space_id"], name=None),
    )
    op.create_table(
        "rerank_profiles",
        sa.Column("profile_id", sa.String(length=80), nullable=False, primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("selection_status", sa.String(length=20), nullable=False),
        sa.Column("security_status", sa.String(length=20), nullable=False),
        sa.Column("availability_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "parser_profiles",
        sa.Column("profile_id", sa.String(length=80), nullable=False, primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("selection_status", sa.String(length=20), nullable=False),
        sa.Column("security_status", sa.String(length=20), nullable=False),
        sa.Column("availability_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "retrieval_profiles",
        sa.Column("profile_id", sa.String(length=80), nullable=False, primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("selection_status", sa.String(length=20), nullable=False),
        sa.Column("security_status", sa.String(length=20), nullable=False),
        sa.Column("availability_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "knowledge_bases",
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("owner_id", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column("embedding_profile_id", sa.String(length=80), nullable=False),
        sa.Column("embedding_profile_version", sa.Integer(), nullable=False),
        sa.Column("scope_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("knowledge_base_id", "embedding_space_id", name="uq_kb_space"),
        sa.ForeignKeyConstraint(["embedding_space_id"], ["embedding_spaces.space_id"], name=None),
        sa.UniqueConstraint("knowledge_base_id", "owner_id", name="uq_kb_owner"),
        sa.UniqueConstraint("owner_id", "name", name="uq_knowledge_base_owner_name"),
    )
    op.create_index("ix_knowledge_bases_owner_id", "knowledge_bases", ["owner_id"], unique=False)
    op.create_index(
        "uq_knowledge_base_default",
        "knowledge_bases",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        sqlite_where=sa.text("is_default"),
    )
    op.create_table(
        "rag_operations",
        sa.Column("operation_id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("owner_id", sa.String(length=120), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("storage_reservation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "scope", "idempotency_key", name="uq_rag_operation_key"),
    )
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("knowledge_base_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("tags_json", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("latest_index_batch_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column("metadata_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.create_foreign_key(
            "fk_documents_knowledge_base",
            "knowledge_bases",
            ["knowledge_base_id"],
            ["knowledge_base_id"],
        )


def downgrade():
    guard_downgrade(op.get_bind())
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_knowledge_base", type_="foreignkey")
        for name in ("knowledge_base_id", "tags_json", "latest_index_batch_id", "metadata_version"):
            batch.drop_column(name)
    for name in (
        "rag_operations",
        "knowledge_bases",
        "retrieval_profiles",
        "parser_profiles",
        "rerank_profiles",
        "embedding_profiles",
        "embedding_spaces",
    ):
        op.drop_table(name)
