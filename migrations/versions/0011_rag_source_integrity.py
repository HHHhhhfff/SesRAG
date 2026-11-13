"""PRD-003：来源状态与批次一致，允许可信确认事务内的中间态。"""

import sqlalchemy as sa
from alembic import op

from migrations.rag_checks import guard_downgrade

revision = "0011_rag_source_integrity"
down_revision = "0010_rag_task_and_run_protocol"
branch_labels = None
depends_on = None


def upgrade():
    # 不修写已有来源事实；不一致的旧库须先诊断，不能猜测来源。
    bind = op.get_bind()
    if bind.scalar(
        sa.text("""SELECT count(*) FROM chunks c JOIN index_builds b
        ON b.index_batch_id=c.index_batch_id
        WHERE c.legacy_unverified<>(b.provenance='legacy_unknown')""")
    ):
        raise RuntimeError("RAG_PROVENANCE_INCONSISTENT: 请先恢复可信来源事实")
    with op.batch_alter_table("index_builds") as batch:
        batch.add_column(
            sa.Column(
                "legacy_unverified",
                sa.Boolean(),
                sa.Computed("provenance = 'legacy_unknown'", persisted=True),
                nullable=False,
            )
        )
        batch.create_unique_constraint(
            "uq_build_provenance", ["index_batch_id", "legacy_unverified"]
        )
        batch.create_check_constraint(
            "ck_build_provenance",
            "provenance IN ('new','legacy_unknown','legacy_confirmed','legacy_verified')",
        )
    with op.batch_alter_table("chunks") as batch:
        batch.drop_constraint("fk_chunks_build_document_space", type_="foreignkey")
        batch.create_foreign_key(
            "fk_chunks_build_document_space",
            "index_builds",
            ["index_batch_id", "document_id", "space_id"],
            ["index_batch_id", "document_id", "space_id"],
            deferrable=True,
            initially="DEFERRED",
        )
        batch.create_foreign_key(
            "fk_chunks_build_provenance",
            "index_builds",
            ["index_batch_id", "legacy_unverified"],
            ["index_batch_id", "legacy_unverified"],
            deferrable=True,
            initially="DEFERRED",
        )
    if bind.dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION rag_build_provenance_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='INSERT' THEN
            IF NEW.provenance='new' THEN RETURN NEW; END IF;
            IF NEW.provenance<>'legacy_verified' THEN
              RAISE EXCEPTION 'BUILD_PROVENANCE_FORGED'; END IF;
          ELSIF OLD.provenance IS NOT DISTINCT FROM NEW.provenance THEN
            RETURN NEW;
          ELSE
            IF OLD.provenance<>'legacy_unknown' OR NEW.provenance<>'legacy_confirmed'
              OR OLD.state<>'succeeded'
              OR (to_jsonb(OLD)-ARRAY['space_id','parse_job_id','artifact_id',
                           'provenance','legacy_unverified'])
                IS DISTINCT FROM
                (to_jsonb(NEW)-ARRAY['space_id','parse_job_id','artifact_id',
                           'provenance','legacy_unverified'])
              THEN RAISE EXCEPTION 'BUILD_PROVENANCE_FORGED'; END IF;
          END IF;
          IF NEW.state<>'succeeded' OR NOT EXISTS (
                SELECT 1 FROM parsed_artifacts a JOIN parse_jobs j USING(parse_job_id)
                JOIN documents d ON d.document_id=NEW.document_id
                JOIN knowledge_bases k ON k.knowledge_base_id=NEW.knowledge_base_id
                JOIN embedding_spaces s ON s.space_id=NEW.space_id
                WHERE a.artifact_id=NEW.artifact_id AND j.parse_job_id=NEW.parse_job_id
                  AND j.document_id=NEW.document_id AND a.source_hash=d.content_hash
                  AND j.source_hash=d.content_hash AND a.parser_hash=j.parser_hash
                  AND a.protocol='legacy_text_reconstruction_v1'
                  AND j.routing_policy_version='legacy_route_v0' AND j.state='succeeded'
                  AND j.parser_kind='local'
                  AND ((TG_OP='UPDATE' AND length(j.parser_snapshot->>'legacy_reference')>0)
                    OR (TG_OP='INSERT' AND j.parser_snapshot->>'legacy_parser'='local_text_v1'
                        AND j.parser_snapshot->>'source_hash'=d.content_hash))
                  AND k.owner_id=d.owner_id AND k.embedding_space_id=NEW.space_id
                  AND s.dimension=384 AND s.descriptor_json->>'model'='mock-384'
                  AND s.descriptor_json->>'revision'='sha256_v1'
              ) THEN RAISE EXCEPTION 'BUILD_PROVENANCE_FORGED'; END IF;
          RETURN NEW;
        END $$""")
        op.execute("""CREATE TRIGGER rag_build_provenance_guard BEFORE INSERT OR UPDATE
            ON index_builds FOR EACH ROW EXECUTE FUNCTION rag_build_provenance_guard()""")
        op.execute("""CREATE FUNCTION rag_chunk_source_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.chunk_id IS DISTINCT FROM NEW.chunk_id
            OR OLD.document_id IS DISTINCT FROM NEW.document_id
            OR OLD.index_batch_id IS DISTINCT FROM NEW.index_batch_id
            OR (OLD.legacy_unverified AND (
              OLD.text IS DISTINCT FROM NEW.text OR OLD.embedding IS DISTINCT FROM NEW.embedding
              OR OLD.seq IS DISTINCT FROM NEW.seq
              OR OLD.start_offset IS DISTINCT FROM NEW.start_offset
              OR OLD.end_offset IS DISTINCT FROM NEW.end_offset
              OR OLD.locations_json::jsonb IS DISTINCT FROM NEW.locations_json::jsonb))
          THEN RAISE EXCEPTION 'CHUNK_SOURCE_IMMUTABLE'; END IF;
          RETURN NEW;
        END $$""")
        op.execute("""CREATE TRIGGER rag_chunk_source_guard BEFORE UPDATE ON chunks
            FOR EACH ROW EXECUTE FUNCTION rag_chunk_source_guard()""")


def downgrade():
    guard_downgrade(op.get_bind())
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER rag_build_provenance_guard ON index_builds")
        op.execute("DROP FUNCTION rag_build_provenance_guard()")
        op.execute("DROP TRIGGER rag_chunk_source_guard ON chunks")
        op.execute("DROP FUNCTION rag_chunk_source_guard()")
    with op.batch_alter_table("chunks") as batch:
        batch.drop_constraint("fk_chunks_build_provenance", type_="foreignkey")
        batch.drop_constraint("fk_chunks_build_document_space", type_="foreignkey")
        batch.create_foreign_key(
            "fk_chunks_build_document_space",
            "index_builds",
            ["index_batch_id", "document_id", "space_id"],
            ["index_batch_id", "document_id", "space_id"],
        )
    with op.batch_alter_table("index_builds") as batch:
        batch.drop_constraint("ck_build_provenance", type_="check")
        batch.drop_constraint("uq_build_provenance", type_="unique")
        batch.drop_column("legacy_unverified")
