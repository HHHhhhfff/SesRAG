"""RAG 迁移的静态数据预检；只使用反射的当前 revision 表。"""

import hashlib
from uuid import uuid4

import sqlalchemy as sa


def table(bind, name):
    return sa.Table(name, sa.MetaData(), autoload_with=bind)


def drain_legacy_docx(bind):
    # 升级前必须停Worker；仍有有效租约时拒绝，不能与旧发布者竞跑。
    tasks, documents = table(bind, "tasks"), table(bind, "documents")
    query = sa.select(tasks.c.task_id).where(
        tasks.c.state.in_(("leased", "running")),
        tasks.c.lease_expires_at > sa.func.current_timestamp(),
    )
    if bind.execute(query).first():
        raise RuntimeError("LEGACY_TASKS_ACTIVE: 请停Worker并等待现有租约结束后再升级")
    ids = bind.execute(
        sa.select(tasks.c.task_id, tasks.c.document_id)
        .join(documents, documents.c.document_id == tasks.c.document_id)
        .where(
            tasks.c.kind == "index_document",
            documents.c.extension == ".docx",
            tasks.c.state.not_in(("succeeded", "failed", "cancelled")),
        )
    ).all()
    for task_id, document_id in ids:
        bind.execute(
            tasks.update()
            .where(tasks.c.task_id == task_id)
            .values(
                state="failed",
                lease_expires_at=None,
                last_error_code="DOCUMENT_WRITE_UPGRADE_REQUIRED",
                last_error_message="DOCX写入请使用v3并确认云端外发",
            )
        )
        bind.execute(
            documents.update()
            .where(documents.c.document_id == document_id)
            .values(
                status=sa.case(
                    (documents.c.active_index_batch_id.is_not(None), "indexed"), else_="failed"
                ),
                last_error_code="DOCUMENT_WRITE_UPGRADE_REQUIRED",
            )
        )


def prepare_legacy_documents(bind):
    documents = table(bind, "documents")
    bases = table(bind, "knowledge_bases")
    owners = bind.execute(sa.select(documents.c.owner_id).distinct()).scalars().all()
    for owner in owners:
        matches = (
            bind.execute(
                sa.select(bases.c.knowledge_base_id).where(
                    bases.c.owner_id == owner, bases.c.is_default.is_(True)
                )
            )
            .scalars()
            .all()
        )
        if len(matches) != 1:
            raise RuntimeError("RAG_BOOTSTRAP_REQUIRED: 每个旧 owner 必须先显式配置唯一默认知识库")
        bind.execute(
            documents.update()
            .where(documents.c.owner_id == owner)
            .values(knowledge_base_id=matches[0])
        )


def backfill_legacy_builds(bind):
    documents, chunks, builds = [table(bind, n) for n in ("documents", "chunks", "index_builds")]
    for doc in bind.execute(sa.select(documents)).mappings():
        batches = set(
            bind.execute(
                sa.select(chunks.c.index_batch_id).where(chunks.c.document_id == doc["document_id"])
            ).scalars()
        )
        if doc["active_index_batch_id"]:
            batches.add(doc["active_index_batch_id"])
        for batch in batches:
            count = bind.scalar(
                sa.select(sa.func.count())
                .select_from(chunks)
                .where(chunks.c.document_id == doc["document_id"], chunks.c.index_batch_id == batch)
            )
            bind.execute(
                builds.insert().values(
                    index_batch_id=batch,
                    document_id=doc["document_id"],
                    knowledge_base_id=doc["knowledge_base_id"],
                    space_id=None,
                    embedding_snapshot={},
                    chunker_snapshot={},
                    state="succeeded" if count else "failed",
                    stage="completed",
                    provenance="legacy_unknown",
                    chunk_count=count,
                    manifest_hash=hashlib.sha256(f"legacy:{batch}".encode()).hexdigest(),
                    error_code=None if count else "LEGACY_EVIDENCE_UNAVAILABLE",
                    created_at=doc["created_at"],
                )
            )
        bind.execute(
            chunks.update()
            .where(chunks.c.document_id == doc["document_id"])
            .values(
                legacy_unverified=True,
                dimension=384,
            )
        )


def protect_legacy_evidence(bind):
    refs, chunks = [table(bind, n) for n in ("legacy_evidence_refs", "chunks")]
    for name, key, payload in [
        ("messages", "message_id", "citations_json"),
        ("context_plans", "context_plan_id", "selected_evidence"),
    ]:
        source = table(bind, name)
        for row in bind.execute(sa.select(source.c[key], source.c[payload])).mappings():
            for item in row[payload] or []:
                if not isinstance(item, dict):
                    continue
                identity = {k: item.get(k) for k in ("document_id", "index_batch_id", "chunk_id")}
                found = bind.scalar(
                    sa.select(chunks.c.chunk_id).where(
                        *[getattr(chunks.c, k) == value for k, value in identity.items()]
                    )
                )
                bind.execute(
                    refs.insert().values(
                        ref_id=str(uuid4()),
                        source_message_id=row[key] if name == "messages" else None,
                        source_plan_id=row[key] if name == "context_plans" else None,
                        identity_json=identity,
                        resolved_chunk_id=found,
                        availability="available" if found else "unavailable",
                    )
                )


def guard_downgrade(bind):
    names = sa.inspect(bind).get_table_names()
    for name in ("parse_jobs", "retrieval_views", "rag_operations"):
        if name in names and bind.scalar(sa.select(sa.func.count()).select_from(table(bind, name))):
            raise RuntimeError("RAG_DOWNGRADE_DATA_PRESENT: 已有本轮业务事实，须一致备份恢复")
    if "index_builds" in names:
        builds = table(bind, "index_builds")
        if bind.scalar(
            sa.select(sa.func.count())
            .select_from(builds)
            .where(builds.c.provenance != "legacy_unknown")
        ):
            raise RuntimeError("RAG_DOWNGRADE_DATA_PRESENT: 已有新构建或空间确认事实")
    if "runs" in names:
        runs = table(bind, "runs")
        if "execution_schema_version" in runs.c and bind.scalar(
            sa.select(sa.func.count()).select_from(runs).where(runs.c.execution_schema_version == 3)
        ):
            raise RuntimeError("RAG_DOWNGRADE_DATA_PRESENT: 已有schema3事实，须一致备份恢复")
    if "chunks" in names:
        chunks = table(bind, "chunks")
        if "dimension" in chunks.c and bind.scalar(
            sa.select(sa.func.count()).select_from(chunks).where(chunks.c.dimension != 384)
        ):
            raise RuntimeError("RAG_DOWNGRADE_DATA_PRESENT: 多维向量不能自动裁剪")
