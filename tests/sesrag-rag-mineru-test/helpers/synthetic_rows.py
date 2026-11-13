"""明确标识的规模夹具：从本例正式发布样本派生合法数据，仅用于范围/性能，非业务成功证据。"""

import copy
from uuid import uuid4

from sqlalchemy import select


def values(row, excluded):
    # 数据库生成列只能由PG计算；规模夹具不能显式写入其投影值。
    return {
        column.name: copy.deepcopy(getattr(row, column.name))
        for column in row.__table__.columns
        if column.name not in excluded and column.computed is None
    }


def seed_published_documents(e, count, start=0):
    from backend.db.models import ChunkModel, DocumentModel
    from backend.db.rag_models import IndexBuildModel

    if not 1 <= count <= 1000:
        raise ValueError("SYNTHETIC_DOCUMENT_LIMIT")
    if start == 0:
        seed = e.upload(raw=b"Synthetic scale fact ALPHA 37")
        base_doc = seed["document_id"]
    else:
        base_doc = e.sql("SELECT document_id FROM documents ORDER BY created_at LIMIT 1")[0][
            "document_id"
        ]

    async def seed_rows():
        async with e.app.state.session_factory() as session:
            template = await session.get(DocumentModel, base_doc)
            build_template = await session.get(IndexBuildModel, template.active_index_batch_id)
            chunk_template = await session.scalar(
                select(ChunkModel).where(ChunkModel.document_id == base_doc)
            )

            for _i in range(1 if start == 0 else 0, count):
                doc_id, batch_id = str(uuid4()), str(uuid4())
                document = DocumentModel(
                    **values(
                        template,
                        {
                            "document_id",
                            "storage_key",
                            "active_index_batch_id",
                            "latest_index_batch_id",
                        },
                    ),
                    document_id=doc_id,
                    storage_key=f"synthetic-scale/{doc_id}.txt",
                    active_index_batch_id=None,
                    latest_index_batch_id=None,
                )
                session.add(document)
                await session.flush()
                batch = IndexBuildModel(
                    **values(
                        build_template,
                        {"index_batch_id", "document_id", "parse_job_id", "artifact_id", "task_id"},
                    ),
                    index_batch_id=batch_id,
                    document_id=doc_id,
                    parse_job_id=None,
                    artifact_id=None,
                    task_id=None,
                )
                session.add(batch)
                await session.flush()
                session.add(
                    ChunkModel(
                        **values(chunk_template, {"chunk_id", "document_id", "index_batch_id"}),
                        chunk_id=str(uuid4()),
                        document_id=doc_id,
                        index_batch_id=batch_id,
                    )
                )
                document.active_index_batch_id = document.latest_index_batch_id = batch_id
            await session.commit()

    e.call(seed_rows)
    e.case.note(
        "准备",
        {"夹具类型": "范围/性能直接持久化，不是端到端成功", "目标文档数": count, "起点": start},
    )
