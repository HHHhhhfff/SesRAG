"""PostgreSQL持久事实保护；静态SQL，不导入运行时ORM。"""

from sqlalchemy import text

IMMUTABLE = (
    "embedding_spaces",
    "parsed_artifacts",
    "parsed_blocks",
    "retrieval_views",
    "retrieval_view_items",
    "evidence_bundles",
    "evidence_components",
    "context_evidence_ranges",
    "message_citation_links",
    "legacy_evidence_refs",
)
PROFILES = ("embedding_profiles", "rerank_profiles", "parser_profiles", "retrieval_profiles")


def install(bind):
    if bind.dialect.name != "postgresql":
        return
    bind.execute(
        text("""CREATE FUNCTION rag_reject_update() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'RAG_IMMUTABLE_FACT'; END $$""")
    )
    for name in IMMUTABLE:
        bind.execute(
            text(
                f"CREATE TRIGGER rag_immutable BEFORE UPDATE ON {name} "
                "FOR EACH ROW EXECUTE FUNCTION rag_reject_update()"
            )
        )
    bind.execute(
        text("""CREATE FUNCTION rag_profile_update() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN IF OLD.profile_id <> NEW.profile_id OR OLD.version <> NEW.version OR
      OLD.config_hash <> NEW.config_hash OR OLD.config_json::jsonb <> NEW.config_json::jsonb THEN
      RAISE EXCEPTION 'PROFILE_VERSION_CONFLICT'; END IF; RETURN NEW; END $$""")
    )
    for name in PROFILES:
        bind.execute(
            text(
                f"CREATE TRIGGER rag_profile_immutable BEFORE UPDATE ON {name} "
                "FOR EACH ROW EXECUTE FUNCTION rag_profile_update()"
            )
        )
    bind.execute(
        text("""CREATE FUNCTION rag_core_update() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_TABLE_NAME='knowledge_bases' THEN
          IF OLD.embedding_space_id<>NEW.embedding_space_id OR OLD.owner_id<>NEW.owner_id OR
             OLD.embedding_profile_id<>NEW.embedding_profile_id OR
             OLD.embedding_profile_version<>NEW.embedding_profile_version
          THEN RAISE EXCEPTION 'EMBEDDING_SPACE_IMMUTABLE'; END IF;
        ELSIF TG_TABLE_NAME='index_builds' THEN
          IF OLD.state='succeeded' AND OLD.provenance<>'legacy_unknown' AND
             to_jsonb(OLD)<>to_jsonb(NEW)
          THEN RAISE EXCEPTION 'INDEX_BUILD_IMMUTABLE'; END IF;
        ELSIF TG_TABLE_NAME='documents' THEN
          IF OLD.owner_id<>NEW.owner_id OR OLD.content_hash<>NEW.content_hash OR
             OLD.storage_key<>NEW.storage_key OR
             OLD.filename<>NEW.filename OR OLD.extension<>NEW.extension OR
             OLD.size_bytes<>NEW.size_bytes OR
             (OLD.knowledge_base_id IS NOT NULL AND
              OLD.knowledge_base_id IS DISTINCT FROM NEW.knowledge_base_id)
          THEN RAISE EXCEPTION 'DOCUMENT_SOURCE_IMMUTABLE'; END IF;
        ELSIF TG_TABLE_NAME='runs' THEN
          IF OLD.execution_schema_version=3 AND
             (OLD.snapshot_json::jsonb<>NEW.snapshot_json::jsonb OR
             OLD.retrieval_view_id IS DISTINCT FROM NEW.retrieval_view_id)
          THEN RAISE EXCEPTION 'RUN_SNAPSHOT_IMMUTABLE'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    )
    for name in ("knowledge_bases", "index_builds", "documents", "runs"):
        bind.execute(
            text(
                f"CREATE TRIGGER rag_core_immutable BEFORE UPDATE ON {name} "
                "FOR EACH ROW EXECUTE FUNCTION rag_core_update()"
            )
        )
    bind.execute(
        text("""CREATE FUNCTION rag_chunk_update() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN IF EXISTS(SELECT 1 FROM index_builds WHERE index_batch_id=OLD.index_batch_id AND
        state='succeeded' AND provenance<>'legacy_unknown') THEN RAISE EXCEPTION 'CHUNK_IMMUTABLE';
        END IF; RETURN NEW; END $$""")
    )
    bind.execute(
        text(
            "CREATE TRIGGER rag_chunk_immutable BEFORE UPDATE ON chunks "
            "FOR EACH ROW EXECUTE FUNCTION rag_chunk_update()"
        )
    )
    bind.execute(
        text(
            "CREATE TRIGGER rag_event_append_only BEFORE UPDATE OR DELETE ON run_events "
            "FOR EACH ROW EXECUTE FUNCTION rag_reject_update()"
        )
    )


def uninstall(bind):
    if bind.dialect.name != "postgresql":
        return
    for name in IMMUTABLE:
        bind.execute(text(f"DROP TRIGGER rag_immutable ON {name}"))
    for name in PROFILES:
        bind.execute(text(f"DROP TRIGGER rag_profile_immutable ON {name}"))
    for name in ("knowledge_bases", "index_builds", "documents", "runs"):
        bind.execute(text(f"DROP TRIGGER rag_core_immutable ON {name}"))
    bind.execute(text("DROP TRIGGER rag_chunk_immutable ON chunks"))
    bind.execute(text("DROP TRIGGER rag_event_append_only ON run_events"))
    for name in ("rag_reject_update", "rag_profile_update", "rag_core_update", "rag_chunk_update"):
        bind.execute(text(f"DROP FUNCTION {name}()"))
