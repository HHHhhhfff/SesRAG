"""新索引任务：短阶段／有界向量批量／候选隔离／有效代原子发布。"""

import hashlib
import json
from dataclasses import asdict
from functools import partial
from uuid import uuid4

from sqlalchemy import select

from backend.application.errors import PermanentTaskError
from backend.application.parse_jobs import advance_parse_job
from backend.application.rag_profiles import resolve_profile
from backend.application.rag_task_execution import lock_build_execution, yield_task
from backend.application.task_execution import check_locked_times, guarded_call
from backend.db.models import ChunkModel, utc_now
from backend.db.rag_models import ParsedArtifactModel, ParsedBlockModel
from backend.domain.rag import NormalizedArtifact, ParsedBlock, digest
from backend.infrastructure.providers.rag_registry import embedding_from_profile
from backend.infrastructure.rag.isolated_processing import isolated


async def load_artifact(session, identity):
    row = await session.get(ParsedArtifactModel, identity)
    if row is None or hashlib.sha256(row.text.encode()).hexdigest() != row.text_hash:
        raise PermanentTaskError("ARTIFACT_UNAVAILABLE", "规范产物缺失或损坏")
    blocks = (
        await session.scalars(
            select(ParsedBlockModel)
            .where(ParsedBlockModel.artifact_id == identity)
            .order_by(ParsedBlockModel.seq)
        )
    ).all()
    return NormalizedArtifact(
        row.text,
        tuple(
            ParsedBlock(
                b.block_id,
                b.kind,
                b.text,
                b.start_offset,
                b.end_offset,
                tuple(b.heading_path),
                tuple(b.locations_json),
            )
            for b in blocks
        ),
        row.protocol,
    )


async def process_index_build_task(
    factory,
    settings,
    task_id,
    worker,
    generation,
    *,
    provider_factory=embedding_from_profile,
    gateway_factory=None,
):
    async with factory() as session:
        task, base, document, build = await lock_build_execution(
            session, task_id, worker, generation
        )
        stage = build.stage
        batch_id, dimension = (
            build.index_batch_id,
            build.embedding_snapshot["config"]["space"]["dimension"],
        )
        snapshot = build.embedding_snapshot
        profile = await resolve_profile(
            session, "embedding", snapshot["profile_id"], snapshot["version"], frozen=True
        )
        if profile.config_json != snapshot["config"] or profile.space_id != build.space_id:
            raise PermanentTaskError("EMBEDDING_SPACE_MISMATCH", "冻结向量空间不一致")
        if stage == "chunk":
            artifact = await load_artifact(session, build.artifact_id)
            chunk_policy = {
                **build.chunker_snapshot,
                "max_bytes": snapshot["config"]["max_input_bytes"],
            }
        if stage == "embed":
            next_seq = task.progress_json.get("next_seq", 0)
            batch = (
                await session.scalars(
                    select(ChunkModel)
                    .where(ChunkModel.index_batch_id == batch_id, ChunkModel.seq >= next_seq)
                    .order_by(ChunkModel.seq)
                    .limit(snapshot["config"]["batch_size"])
                )
            ).all()
            inputs = tuple(row.text for row in batch)
            batch_ids = tuple(row.chunk_id for row in batch)
    if stage == "parse":
        kwargs = {} if gateway_factory is None else {"gateway_factory": gateway_factory}
        await advance_parse_job(factory, settings, task_id, worker, generation, **kwargs)
        return
    if stage == "chunk":
        drafts = await guarded_call(
            factory,
            task_id,
            worker,
            generation,
            partial(
                isolated,
                "chunk",
                json.dumps(asdict(artifact), ensure_ascii=False).encode(),
                ".md",
                filename=json.dumps(chunk_policy),
                timeout=30,
            ),
            timeout=35,
        )
        if not drafts:
            raise PermanentTaskError("EMPTY_DOCUMENT", "没有有效切片")
        async with factory() as session:
            task, _, document, build = await lock_build_execution(
                session, task_id, worker, generation
            )
            for draft in drafts:
                session.add(
                    ChunkModel(
                        chunk_id=str(uuid4()),
                        document_id=document.document_id,
                        index_batch_id=batch_id,
                        seq=draft.seq,
                        text=draft.text,
                        start_offset=draft.start,
                        end_offset=draft.end,
                        embedding=None,
                        dimension=dimension,
                        space_id=build.space_id,
                        content_hash=hashlib.sha256(draft.text.encode()).hexdigest(),
                        locations_json=list(draft.locations),
                        block_segments_json=list(draft.block_segments),
                    )
                )
            task.progress_json = {"next_seq": 0, "total_chunks": len(drafts)}
            build.stage, build.state = "embed", "building"
            await yield_task(session, task)
        return
    if stage == "embed":
        if not inputs:
            raise PermanentTaskError("INDEX_MANIFEST_INVALID", "向量检查点缺少候选片段")
        vectors = await guarded_call(
            factory,
            task_id,
            worker,
            generation,
            partial(provider_factory(snapshot).embed, inputs, purpose="document"),
        )
        if len(vectors) != len(inputs):
            raise PermanentTaskError("EMBEDDING_PROTOCOL_INVALID", "向量数量与切片不一致")
        async with factory() as session:
            task, _, document, build = await lock_build_execution(
                session, task_id, worker, generation
            )
            for identity, vector in zip(batch_ids, vectors, strict=True):
                from backend.application.vector_validation import validate_vector

                row = await session.get(ChunkModel, identity)
                if row is None or row.index_batch_id != batch_id or row.embedding is not None:
                    raise PermanentTaskError("INDEX_MANIFEST_INVALID", "候选片段与检查点不一致")
                row.embedding = validate_vector(vector, dimension=dimension)
            completed = next_seq + len(inputs)
            task.progress_json = {**task.progress_json, "next_seq": completed}
            build.stage = "publish" if completed == task.progress_json["total_chunks"] else "embed"
            build.chunk_count, build.state = completed, "building"
            await yield_task(session, task)
        return
    if stage == "publish":
        async with factory() as session:
            task, base, document, build = await lock_build_execution(
                session, task_id, worker, generation
            )
            rows = (
                await session.scalars(
                    select(ChunkModel)
                    .where(ChunkModel.index_batch_id == batch_id)
                    .order_by(ChunkModel.seq)
                )
            ).all()
            if (
                not rows
                or len(rows) != task.progress_json["total_chunks"]
                or any(
                    row.seq != i
                    or row.space_id != build.space_id
                    or row.dimension != dimension
                    or row.embedding is None
                    or hashlib.sha256(row.text.encode()).hexdigest() != row.content_hash
                    for i, row in enumerate(rows)
                )
            ):
                raise PermanentTaskError("INDEX_MANIFEST_INVALID", "候选批次不完整")
            lease, deadline = task.lease_expires_at, task.deadline_at
            build.manifest_hash = digest(
                {
                    "artifact": build.artifact_id,
                    "source": document.content_hash,
                    "embedding": snapshot,
                    "chunker": build.chunker_snapshot,
                    "chunks": [row.content_hash for row in rows],
                }
            )
            build.state, build.stage, build.published_at = "succeeded", "completed", utc_now()
            document.active_index_batch_id, document.status, document.last_error_code = (
                batch_id,
                "indexed",
                None,
            )
            base.scope_revision += 1
            task.state, task.lease_expires_at = "succeeded", None
            await session.flush()
            check_locked_times(lease, deadline)
            await session.commit()
        return
    raise PermanentTaskError("INDEX_STAGE_INVALID", "索引检查点无效")
