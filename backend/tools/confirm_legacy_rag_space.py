"""显式确认旧Mock-384来源；默认预检，不把未知向量按维度自动归类。"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from backend.application.errors import ApplicationError
from backend.application.legacy_rag import LEGACY_SPACE
from backend.application.vector_validation import validate_vector
from backend.config import Settings
from backend.db.models import ChunkModel, DocumentModel
from backend.db.rag_models import (
    IndexBuildModel,
    KnowledgeBaseModel,
    ParsedArtifactModel,
    ParsedBlockModel,
    ParseJobModel,
)
from backend.db.session import create_engine, create_session_factory
from backend.domain.rag import digest


async def confirm(session, settings, manifest, *, apply=False):
    if (
        set(manifest) != {"space_id", "provenance_reference", "batches"}
        or manifest["space_id"] != LEGACY_SPACE.space_id
        or not manifest["provenance_reference"]
        or not 1 <= len(manifest["batches"]) <= 1000
    ):
        raise ValueError("仅支持有可信部署证据的旧Mock-384；清单需明确space/provenance/batches")
    reports = []
    for item in manifest["batches"]:
        document = await session.get(DocumentModel, item["document_id"])
        build = await session.get(IndexBuildModel, item["index_batch_id"])
        if (
            document is None
            or document.owner_id != settings.owner_id
            or build is None
            or build.document_id != document.document_id
            or item["source_hash"] != document.content_hash
        ):
            raise ValueError("旧批次归属或源hash不一致")
        base = await session.scalar(
            select(KnowledgeBaseModel)
            .where(KnowledgeBaseModel.knowledge_base_id == build.knowledge_base_id)
            .with_for_update()
        )
        if (
            base.embedding_space_id != LEGACY_SPACE.space_id
            or build.provenance not in {"legacy_unknown", "legacy_confirmed"}
            or build.state != "succeeded"
        ):
            raise ValueError("旧批次不在指定可信空间内")
        if build.provenance == "legacy_confirmed":
            reports.append({"index_batch_id": build.index_batch_id, "state": "already_confirmed"})
            continue
        chunks = (
            await session.scalars(
                select(ChunkModel)
                .where(ChunkModel.index_batch_id == build.index_batch_id)
                .order_by(ChunkModel.seq)
            )
        ).all()
        if not chunks or max(c.end_offset for c in chunks) > 32 * 1024**2:
            raise ValueError("缺少旧片段或范围超限，不伪造恢复")
        text = ""
        for chunk in chunks:
            validate_vector(list(chunk.embedding), dimension=384)
            if chunk.start_offset > len(text) or chunk.end_offset - chunk.start_offset != len(
                chunk.text
            ):
                raise ValueError("旧文本存在不可恢复的空洞")
            overlap = min(len(text), chunk.end_offset) - chunk.start_offset
            if text[chunk.start_offset : chunk.start_offset + overlap] != chunk.text[:overlap]:
                raise ValueError("旧片段重叠内容不一致")
            text += chunk.text[max(0, overlap) :]
        reports.append(
            {
                "index_batch_id": build.index_batch_id,
                "state": "confirmed" if apply else "would_confirm",
                "chunks": len(chunks),
            }
        )
        if not apply:
            continue
        job_id, artifact_id = str(uuid4()), str(uuid4())
        parser_hash = digest(
            {"legacy_reference": manifest["provenance_reference"], "source": document.content_hash}
        )
        job = ParseJobModel(
            parse_job_id=job_id,
            document_id=document.document_id,
            source_hash=document.content_hash,
            parser_kind="local",
            routing_policy_version="legacy_route_v0",
            parser_snapshot={"legacy_reference": manifest["provenance_reference"]},
            parser_hash=parser_hash,
            state="succeeded",
            stage="completed",
        )
        session.add(job)
        await session.flush()
        artifact = ParsedArtifactModel(
            artifact_id=artifact_id,
            parse_job_id=job_id,
            source_hash=document.content_hash,
            parser_hash=parser_hash,
            protocol="legacy_text_reconstruction_v1",
            text=text,
            text_hash=hashlib.sha256(text.encode()).hexdigest(),
            manifest_hash=digest(item),
            unsupported_json=["legacy_positions_not_reverified"],
        )
        session.add(artifact)
        await session.flush()
        for chunk in chunks:
            block_id = str(uuid4())
            session.add(
                ParsedBlockModel(
                    block_id=block_id,
                    artifact_id=artifact_id,
                    seq=chunk.seq,
                    kind="legacy_text",
                    text=chunk.text,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    heading_path=[],
                    locations_json=[],
                )
            )
            chunk.space_id, chunk.dimension, chunk.legacy_unverified = (
                LEGACY_SPACE.space_id,
                384,
                False,
            )
            chunk.content_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
            chunk.block_segments_json = [
                {"block_id": block_id, "start": chunk.start_offset, "end": chunk.end_offset}
            ]
        await session.flush()
        job.artifact_id = artifact_id
        build.space_id, build.parse_job_id, build.artifact_id, build.provenance = (
            LEGACY_SPACE.space_id,
            job_id,
            artifact_id,
            "legacy_confirmed",
        )
    if apply:
        await session.commit()
    return reports


async def main(args):
    settings = Settings()
    source = Path(args.manifest)
    if source.stat().st_size > 1024**2:
        raise ValueError("清单超过1MiB")
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as session:
            print(
                json.dumps(
                    await confirm(
                        session,
                        settings,
                        json.loads(source.read_text(encoding="utf-8")),
                        apply=args.apply,
                    ),
                    ensure_ascii=False,
                )
            )
    except (ValueError, ApplicationError):
        raise SystemExit(
            "LEGACY_CONFIRMATION_REJECTED: 请核对可信部署记录、归属及现存片段；未提交更改"
        ) from None
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args()))
