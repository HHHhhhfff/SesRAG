"""诊断和Run共用的检索编排；失败不伪装成空结果。"""

import hashlib
import time
from dataclasses import replace
from datetime import timedelta
from functools import partial
from uuid import uuid4

from sqlalchemy import select

from backend.application.errors import ApplicationError, PermanentTaskError
from backend.application.evidence_assembly import assemble_evidence
from backend.application.rag_operations import record, replay
from backend.application.rag_profiles import resolve_profile
from backend.application.retrieval_views import freeze_retrieval, load_scope
from backend.application.source_locations import clip_locations, public_locations
from backend.db.models import ChunkModel, TaskModel, utc_now
from backend.db.rag_models import (
    EvidenceBundleModel,
    EvidenceComponentModel,
    IndexBuildModel,
    ParsedArtifactModel,
    RetrievalExecutionModel,
    RetrievalViewModel,
)
from backend.domain.rag import RetrievalPolicy, RetrievalResult, digest
from backend.infrastructure.providers.rag_registry import (
    embedding_from_profile,
    rerank_from_profile,
)
from backend.infrastructure.rag.artifact_store import ArtifactStore
from backend.infrastructure.rag.vector_search import VectorSearch


async def validate_frozen_retrieval(factory, settings, scope, snapshot):
    """每次外发前重查安全禁用；冻结配置不漂移，但不冻结已撤销的调用授权。"""
    async with factory() as session:
        retrieval_profile = snapshot["retrieval_profile"]
        current_retrieval = await resolve_profile(
            session,
            "retrieval",
            retrieval_profile["profile_id"],
            retrieval_profile["version"],
            frozen=True,
        )
        if current_retrieval.config_hash != retrieval_profile["config_hash"]:
            raise PermanentTaskError("PROFILE_VERSION_CONFLICT", "冻结检索策略不一致")
        for kind, frozen in [
            ("embedding", snapshot["embedding"]),
            ("rerank", snapshot.get("rerank")),
        ]:
            if frozen:
                current = await resolve_profile(
                    session, kind, frozen["profile_id"], frozen["version"], frozen=True
                )
                if current.config_json != frozen["config"]:
                    raise PermanentTaskError("PROFILE_VERSION_CONFLICT", "冻结配置不一致")
        await load_scope(session, settings, scope.view_id)


async def execute_retrieval(
    factory,
    settings,
    scope,
    snapshot,
    query,
    guarded,
    *,
    embedding_factory=embedding_from_profile,
    rerank_factory=rerank_from_profile,
    progress=None,
):
    policy = RetrievalPolicy.model_validate(snapshot["policy"])
    embedding = snapshot["embedding"]
    if not query.strip() or len(query.encode()) > embedding["config"]["max_input_bytes"]:
        raise PermanentTaskError("RETRIEVAL_QUERY_TOO_LONG", "问题为空或超过向量输入预算")
    await validate_frozen_retrieval(factory, settings, scope, snapshot)
    timings = {}
    if not scope.batches:
        return RetrievalResult("empty", (), (), timings=timings)
    started = time.monotonic()
    if progress:
        await progress("query_embedding")
    await validate_frozen_retrieval(factory, settings, scope, snapshot)
    vectors = await guarded(partial(embedding_factory(embedding).embed, (query,), purpose="query"))
    timings["query_embedding_ms"] = (time.monotonic() - started) * 1000
    started = time.monotonic()
    if progress:
        await progress("dense_search")
    async with factory() as session:
        candidates = await VectorSearch(session).search(scope, vectors[0], policy.candidate_k)
    timings["dense_ms"] = (time.monotonic() - started) * 1000
    ordered = candidates
    mode, error = "ok", None
    if policy.rerank_enabled and candidates:
        if progress:
            await progress("rerank")
        if not snapshot.get("rerank"):
            raise PermanentTaskError("PROFILE_UNAVAILABLE", "冻结重排配置缺失")
        await validate_frozen_retrieval(factory, settings, scope, snapshot)
        started = time.monotonic()
        try:
            ranker = rerank_factory(snapshot["rerank"])
            ranking = await guarded(
                partial(
                    ranker.rank,
                    query,
                    tuple(h.text for h in candidates),
                )
            )
            if sorted(i for i, _ in ranking) != list(range(len(candidates))):
                raise PermanentTaskError("RERANK_PROTOCOL_INVALID", "重排返回候选不完整")
            ranges = getattr(ranker, "input_ranges", tuple((0, len(c.text)) for c in candidates))
            scores = {i: score for i, score in ranking}
            candidates = tuple(
                replace(
                    c,
                    rerank_score=scores[i],
                    rerank_input_start=ranges[i][0],
                    rerank_input_end=ranges[i][1],
                )
                for i, c in enumerate(candidates)
            )
            ordered = tuple(candidates[i] for i, _ in ranking)
        except ApplicationError as exc:
            if policy.failure_policy != "dense_fallback" or exc.code not in {
                "RERANK_TEMPORARY_UNAVAILABLE",
                "RERANK_SERVICE_FAILED",
                "RERANK_PROTOCOL_INVALID",
                "RERANK_INPUT_BUDGET_EXCEEDED",
                "UPSTREAM_TEMPORARY_UNAVAILABLE",
            }:
                raise
            mode, error = "degraded", exc.code
        timings["rerank_ms"] = (time.monotonic() - started) * 1000
    if progress:
        await progress("enhancement")
    async with factory() as session:
        bundles, omitted = await assemble_evidence(session, ordered[: policy.top_k], policy)
    return RetrievalResult(
        mode if candidates else "empty", bundles, candidates, omitted, error, timings
    )


async def persist_bundles(session, execution, result):
    for bundle in result.bundles:
        session.add(
            EvidenceBundleModel(
                bundle_id=bundle["bundle_id"],
                execution_id=execution.execution_id,
                document_id=bundle["document_id"],
                index_batch_id=bundle["index_batch_id"],
                anchors_json=bundle["anchors"],
                dense_score=bundle["dense_score"],
                rerank_score=bundle["rerank_score"],
            )
        )
        await session.flush()
        for seq, component in enumerate(bundle["components"]):
            session.add(EvidenceComponentModel(**component, bundle_id=bundle["bundle_id"], seq=seq))
    execution.state, execution.stage, execution.mode = "succeeded", "completed", result.mode
    execution.error_code = result.error_code
    execution.candidates_json = [
        {
            k: getattr(hit, k)
            for k in (
                "chunk_id",
                "document_id",
                "index_batch_id",
                "dense_score",
                "rerank_score",
                "rerank_input_start",
                "rerank_input_end",
            )
        }
        for hit in result.candidates
    ]
    execution.omitted_json, execution.timings_json = list(result.omitted), result.timings


async def create_diagnostic(session, settings, payload, key):
    hashed = digest(payload.model_dump(mode="json"))
    existing = await replay(session, settings.owner_id, "diagnostic", key, hashed)
    if existing:
        return await load_execution(session, settings, existing["execution_id"]), True
    scope, snapshot = await freeze_retrieval(session, settings, payload)
    from backend.application.rag_capacity import reserve_storage

    await reserve_storage(session, settings, source_bytes=len(payload.query.encode()))
    if len(payload.query.encode()) > snapshot["embedding"]["config"]["max_input_bytes"]:
        raise ApplicationError("RETRIEVAL_QUERY_TOO_LONG", "诊断问题超过向量输入预算", 422)
    identity = str(uuid4())
    store = ArtifactStore(settings.rag_artifact_dir)
    private_key = f"diagnostic-{identity}.bin"
    store.write(private_key, payload.query.encode())
    try:
        execution = RetrievalExecutionModel(
            execution_id=identity,
            view_id=scope.view_id,
            origin="diagnostic",
            snapshot_json=snapshot,
            query_hash=hashlib.sha256(payload.query.encode()).hexdigest(),
            private_query_key=private_key,
        )
        session.add(execution)
        await session.flush()
        task = TaskModel(
            task_id=str(uuid4()),
            kind="retrieval_diagnostic",
            retrieval_execution_id=identity,
            state="queued",
            max_attempts=3,
            deadline_at=utc_now() + timedelta(seconds=120),
        )
        session.add(task)
        await session.flush()
        execution.task_id = task.task_id
        record(session, settings.owner_id, "diagnostic", key, hashed, {"execution_id": identity})
        await session.commit()
        return execution, False
    except Exception:
        await session.rollback()
        store.path(private_key).unlink(missing_ok=True)
        raise


async def load_execution(session, settings, identity):
    row = await session.scalar(
        select(RetrievalExecutionModel)
        .join(RetrievalViewModel, RetrievalViewModel.view_id == RetrievalExecutionModel.view_id)
        .where(
            RetrievalExecutionModel.execution_id == identity,
            RetrievalViewModel.owner_id == settings.owner_id,
        )
    )
    if row is None:
        from backend.application.rag_retention import check_expired

        await check_expired(session, settings, identity)
        raise ApplicationError("RETRIEVAL_NOT_FOUND", "检索记录不存在", 404)
    return row


async def project_execution(session, row):
    ids = (
        await session.scalars(
            select(EvidenceBundleModel.bundle_id)
            .where(EvidenceBundleModel.execution_id == row.execution_id)
            .order_by(EvidenceBundleModel.bundle_id)
        )
    ).all()
    return {
        "execution_id": row.execution_id,
        "view_id": row.view_id,
        "origin": row.origin,
        "state": row.state,
        "stage": row.stage,
        "mode": row.mode,
        "candidates": row.candidates_json,
        "bundle_ids": list(ids),
        "omitted": row.omitted_json,
        "error_code": row.error_code,
        "timings_ms": row.timings_json,
        "profile": {
            "retrieval_profile_id": row.snapshot_json["retrieval_profile"]["profile_id"],
            "retrieval_profile_version": row.snapshot_json["retrieval_profile"]["version"],
            "candidate_k": row.snapshot_json["policy"]["candidate_k"],
            "top_k": row.snapshot_json["policy"]["top_k"],
        },
    }


async def read_bundle(session, settings, identity, offset=0):
    row = await session.get(EvidenceBundleModel, identity)
    if row is None:
        from backend.application.rag_retention import check_expired

        await check_expired(session, settings, identity)
        raise ApplicationError("EVIDENCE_NOT_FOUND", "证据不存在", 404)
    await load_execution(session, settings, row.execution_id)
    build = await session.get(IndexBuildModel, row.index_batch_id)
    artifact = await session.get(ParsedArtifactModel, build.artifact_id) if build else None
    components = (
        await session.scalars(
            select(EvidenceComponentModel)
            .where(EvidenceComponentModel.bundle_id == identity)
            .order_by(EvidenceComponentModel.seq)
        )
    ).all()
    if artifact is None or not components:
        raise ApplicationError("EVIDENCE_UNAVAILABLE", "证据内容缺失", 409)
    if (
        build.document_id != row.document_id
        or hashlib.sha256(artifact.text.encode()).hexdigest() != artifact.text_hash
    ):
        raise ApplicationError("EVIDENCE_UNAVAILABLE", "证据产物身份或hash不匹配", 409)
    start, end = min(c.start_offset for c in components), max(c.end_offset for c in components)
    text = artifact.text[start:end]
    locations = []
    for component in components:
        chunk = await session.get(ChunkModel, component.chunk_id)
        if (
            chunk is None
            or chunk.document_id != row.document_id
            or chunk.index_batch_id != row.index_batch_id
            or not chunk.start_offset
            <= component.start_offset
            < component.end_offset
            <= chunk.end_offset
            or hashlib.sha256(
                artifact.text[component.start_offset : component.end_offset].encode()
            ).hexdigest()
            != component.content_hash
        ):
            raise ApplicationError("EVIDENCE_UNAVAILABLE", "证据组件身份或hash不匹配", 409)
        locations.extend(
            public_locations(
                chunk.locations_json, chunk.chunk_id, chunk.start_offset, chunk.end_offset
            )
        )
    return {
        "schema_version": 2,
        "bundle_id": identity,
        "document_id": row.document_id,
        "index_batch_id": row.index_batch_id,
        "text": text[offset : offset + 4000],
        "components": [
            {
                k: getattr(c, k)
                for k in ("component_id", "chunk_id", "start_offset", "end_offset", "content_hash")
            }
            for c in components
        ],
        "locations": clip_locations(locations, start, end, artifact.text),
        "dense_score": row.dense_score,
        "rerank_score": row.rerank_score,
        "next_offset": offset + 4000 if offset + 4000 < len(text) else None,
    }
