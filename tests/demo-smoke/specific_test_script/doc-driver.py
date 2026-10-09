"""DOC_003/DOC_005：调用生产登记/存储函数，仅操作本次临时数据。"""

import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.documents import MAX_DOCUMENT_BYTES, create_document
from backend.config import Settings
from backend.db.models import DocumentModel, TaskModel
from backend.db.session import create_engine


async def main():
    settings = Settings()
    engine = create_engine(settings)
    result = {}
    # DOC_003：真实生产 commit 使用 savepoint；外层回滚保证 Worker 看不到大索引任务。
    try:
        with tempfile.TemporaryDirectory(prefix="doc-003-") as directory:
            local = settings.model_copy(update={"upload_dir": str(Path(directory) / "uploads")})
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    async with AsyncSession(
                        bind=connection,
                        expire_on_commit=False,
                        join_transaction_mode="create_savepoint",
                    ) as session:
                        content = b"a" * MAX_DOCUMENT_BYTES
                        document, task = await create_document(
                            session, local, "doc-003-limit.txt", "text/plain", content
                        )
                        saved = await session.get(DocumentModel, document.document_id)
                        queued = await session.get(TaskModel, task.task_id)
                        stored = local.upload_path / saved.storage_key
                        result = {
                            "size": saved.size_bytes,
                            "hash": saved.content_hash,
                            "expected_hash": hashlib.sha256(content).hexdigest(),
                            "stored_size": stored.stat().st_size,
                            "document_status": saved.status,
                            "task_state": queued.state,
                            "task_kind": queued.kind,
                            "task_document": queued.document_id == saved.document_id,
                            "batch_present": bool(queued.progress_json.get("index_batch_id")),
                        }
                        # DOC_005：同一临时范围的旁路哨兵不得被恶意原文件名覆盖。
                        sentinel = Path(directory) / "sentinel.txt"
                        sentinel.write_bytes(b"DOC_005-original-sentinel")
                        sentinel_hash = hashlib.sha256(sentinel.read_bytes()).hexdigest()
                        result["sentinel_checks"] = []
                        for filename in (
                            "../sentinel.txt",
                            str(sentinel),
                            "中文 ☃ 特殊&.txt",
                        ):
                            candidate, _task = await create_document(
                                session, local, filename, "text/plain", b"DOC_005-upload"
                            )
                            result["sentinel_checks"].append(
                                {
                                    "server_uuid_key": candidate.storage_key
                                    == f"documents/{candidate.document_id}/source.txt",
                                    "under_upload_root": local.upload_path.resolve()
                                    in (local.upload_path / candidate.storage_key)
                                    .resolve()
                                    .parents,
                                    "sentinel_unchanged": hashlib.sha256(
                                        sentinel.read_bytes()
                                    ).hexdigest()
                                    == sentinel_hash,
                                }
                            )
                finally:
                    await transaction.rollback()
                async with AsyncSession(bind=connection) as session:
                    result["rollback_document_absent"] = (
                        await session.get(DocumentModel, document.document_id) is None
                    )
                    result["rollback_task_absent"] = (
                        await session.get(TaskModel, task.task_id) is None
                    )
    finally:
        await engine.dispose()
    print("SMOKE_JSON:" + json.dumps(result, ensure_ascii=False))


asyncio.run(main())
