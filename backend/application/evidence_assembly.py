"""同文档／同批次合并规范文本范围；记录真实组成与预算去除。"""

import hashlib
from uuid import uuid4

from sqlalchemy import select

from backend.application.errors import PermanentTaskError
from backend.application.source_locations import clip_locations, public_locations
from backend.db.models import ChunkModel
from backend.db.rag_models import IndexBuildModel, ParsedArtifactModel


async def assemble_evidence(session, hits, policy):
    groups = []
    omitted = []
    for rank, hit in enumerate(hits):
        neighbors = (
            await session.scalars(
                select(ChunkModel)
                .where(
                    ChunkModel.document_id == hit.document_id,
                    ChunkModel.index_batch_id == hit.index_batch_id,
                    ChunkModel.seq.between(
                        max(0, hit.seq - policy.neighbor_radius), hit.seq + policy.neighbor_radius
                    ),
                )
                .order_by(ChunkModel.seq)
            )
        ).all()
        if not neighbors:
            raise PermanentTaskError("EVIDENCE_UNAVAILABLE", "命中来源片段缺失")
        start, end = min(c.start_offset for c in neighbors), max(c.end_offset for c in neighbors)
        matched = [
            g
            for g in groups
            if g["document_id"] == hit.document_id
            and g["index_batch_id"] == hit.index_batch_id
            and g["end"] >= start
            and end >= g["start"]
        ]
        if matched:
            group = matched[0]
            group["start"], group["end"] = min(group["start"], start), max(group["end"], end)
            group["chunks"].update({c.chunk_id: c for c in neighbors})
            group["anchors"].append(hit.chunk_id)
            for other in matched[1:]:
                group["start"], group["end"] = (
                    min(group["start"], other["start"]),
                    max(group["end"], other["end"]),
                )
                group["chunks"].update(other["chunks"])
                group["anchors"].extend(other["anchors"])
                groups.remove(other)
        else:
            groups.append(
                {
                    "document_id": hit.document_id,
                    "index_batch_id": hit.index_batch_id,
                    "start": start,
                    "end": end,
                    "chunks": {c.chunk_id: c for c in neighbors},
                    "anchors": [hit.chunk_id],
                    "rank": rank,
                    "dense_score": hit.dense_score,
                    "rerank_score": hit.rerank_score,
                }
            )
    bundles = []
    budget = policy.max_enhanced_chars
    components_left = 100
    for group in sorted(groups, key=lambda g: g["rank"]):
        if budget <= 0 or components_left <= 0:
            omitted.extend(
                {"chunk_id": c, "reason": "enhancement_budget"} for c in group["anchors"]
            )
            continue
        build = await session.get(IndexBuildModel, group["index_batch_id"])
        artifact = await session.get(ParsedArtifactModel, build.artifact_id) if build else None
        if artifact is None:
            raise PermanentTaskError("EVIDENCE_UNAVAILABLE", "规范产物不可读取")
        start, end = group["start"], min(group["end"], group["start"] + budget)
        components = []
        locations = []
        for chunk in sorted(group["chunks"].values(), key=lambda c: (c.seq, c.chunk_id)):
            left, right = max(start, chunk.start_offset), min(end, chunk.end_offset)
            if right <= left:
                continue
            if components_left <= 0:
                end = min(end, max(c["end_offset"] for c in components))
                break
            components.append(
                {
                    "component_id": str(uuid4()),
                    "chunk_id": chunk.chunk_id,
                    "start_offset": left,
                    "end_offset": right,
                    "content_hash": hashlib.sha256(artifact.text[left:right].encode()).hexdigest(),
                }
            )
            locations.extend(
                public_locations(
                    chunk.locations_json, chunk.chunk_id, chunk.start_offset, chunk.end_offset
                )
            )
            components_left -= 1
        text = artifact.text[start:end]
        if not text.strip():
            continue
        budget -= len(text)
        bundles.append(
            {
                "bundle_id": str(uuid4()),
                "document_id": group["document_id"],
                "index_batch_id": group["index_batch_id"],
                "anchors": group["anchors"],
                "dense_score": group["dense_score"],
                "rerank_score": group["rerank_score"],
                "text": text,
                "start_offset": start,
                "end_offset": end,
                "components": components,
                "locations": clip_locations(locations, start, end, artifact.text),
            }
        )
        if end < group["end"]:
            omitted.extend(
                {"chunk_id": c, "reason": "enhancement_truncated"} for c in group["anchors"]
            )
    return tuple(bundles), tuple(omitted)
