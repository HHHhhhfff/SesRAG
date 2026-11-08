"""一次有效 Worker 调用推进一个解析阶段，等待通过持久队列让出。"""

import hashlib
import time
from datetime import timedelta, timezone
from functools import partial
from uuid import uuid4

from backend.application.errors import PermanentTaskError, TransientTaskError
from backend.application.rag_profiles import profile_reason, resolve_profile
from backend.application.rag_task_execution import lock_build_execution, yield_task
from backend.application.task_execution import check_locked_times, guarded_call
from backend.db.models import utc_now
from backend.db.rag_models import ParsedArtifactModel, ParsedBlockModel, ParseJobModel
from backend.domain.rag import digest
from backend.infrastructure.rag.artifact_store import ArtifactStore
from backend.infrastructure.rag.isolated_processing import isolated
from backend.infrastructure.rag.mineru_client import MinerUClient
from backend.infrastructure.storage.local_files import LocalFileStorage


async def advance_parse_job(
    factory, settings, task_id, worker, generation, *, gateway_factory=MinerUClient
):
    lease_guarded = partial(guarded_call, factory, task_id, worker, generation)
    store = ArtifactStore(settings.rag_artifact_dir, settings.mineru_state_encryption_key)
    async with factory() as session:
        task, _, document, build = await lock_build_execution(session, task_id, worker, generation)
        job = await session.get(ParseJobModel, build.parse_job_id)
        if job.state == "succeeded":
            build.artifact_id, build.stage, build.state = job.artifact_id, "chunk", "building"
            await yield_task(session, task)
            return
        if job.state in {"failed", "cancelled"}:
            raise PermanentTaskError(job.error_code or "PARSE_FAILED", "解析已结束，不能重复执行")
        snapshot, route = job.parser_snapshot, job.parser_kind
        profile = await resolve_profile(
            session, "parser", snapshot["profile_id"], snapshot["version"], frozen=True
        )
        if (
            digest(
                {
                    "profile_id": profile.profile_id,
                    "version": profile.version,
                    "config": profile.config_json,
                }
            )
            != job.parser_hash
        ):
            raise PermanentTaskError("PROFILE_VERSION_CONFLICT", "冻结解析配置损坏")
        reason = profile_reason("parser", snapshot["config"], settings, document.extension)
        if reason:
            raise PermanentTaskError(reason, "办公解析当前不可用")
        if job.parse_deadline is None:
            job.parse_deadline = min(
                task.deadline_at.replace(tzinfo=timezone.utc),
                utc_now()
                + timedelta(
                    seconds=snapshot["config"]["parse_timeout"] if route == "mineru" else 30
                ),
            )
        remaining = (job.parse_deadline.replace(tzinfo=timezone.utc) - utc_now()).total_seconds()
        if remaining <= 0:
            raise PermanentTaskError(
                "MINERU_ATTEMPT_TIMEOUT" if route == "mineru" else "DOCUMENT_PARSE_LIMIT",
                "解析达到截止时间",
            )
        stage = job.stage
        if route == "mineru" and stage == "submitting":
            # 此阶段只在远端申请前提交一次；重启无法知道应答便保守停止。
            raise PermanentTaskError("MINERU_SUBMISSION_UNKNOWN", "提交结果未知，不自动重新申请")
        if stage == "preparing":
            job.stage = "local_parsing" if route == "local" else "submitting"
            job.submission_nonce = str(uuid4()) if route == "mineru" else None
        job.state = "running"
        build.state = "building"
        source_key, source_hash, extension, filename, job_id = (
            document.storage_key,
            document.content_hash,
            document.extension,
            document.filename,
            job.parse_job_id,
        )
        state_key, batch_id = job.private_state_key, job.remote_batch_id
        lease, deadline = task.lease_expires_at, task.deadline_at
        await session.flush()
        check_locked_times(lease, deadline)
        await session.commit()
    phase_deadline = time.monotonic() + remaining

    async def guarded(operation, *, timeout=30):
        left = phase_deadline - time.monotonic()
        if left <= 0:
            raise PermanentTaskError(
                "MINERU_ATTEMPT_TIMEOUT" if route == "mineru" else "DOCUMENT_PARSE_LIMIT",
                "解析达到截止时间",
            )
        try:
            return await lease_guarded(operation, timeout=min(timeout, left))
        except TimeoutError:
            if time.monotonic() >= phase_deadline:
                raise PermanentTaskError(
                    "MINERU_ATTEMPT_TIMEOUT" if route == "mineru" else "DOCUMENT_PARSE_LIMIT",
                    "解析达到截止时间",
                ) from None
            if route == "mineru" and stage == "preparing":
                raise PermanentTaskError(
                    "MINERU_SUBMISSION_UNKNOWN", "申请结果未知，不自动重提"
                ) from None
            raise TransientTaskError(
                "MINERU_TEMPORARY_UNAVAILABLE" if route == "mineru" else "DOCUMENT_PARSE_LIMIT",
                "解析步骤超时",
            ) from None

    artifact = None
    handle = None
    observation = None
    next_stage = None
    delay = 0
    if route == "local":
        raw = await guarded(
            partial(LocalFileStorage(settings.upload_path).read, source_key),
            timeout=min(30, remaining),
        )
        if hashlib.sha256(raw).hexdigest() != source_hash:
            raise PermanentTaskError("SOURCE_HASH_MISMATCH", "原源hash不匹配")
        artifact = await guarded(
            partial(isolated, "text", raw, extension, timeout=min(30, remaining)),
            timeout=min(30, remaining),
        )
    else:
        gateway = gateway_factory(settings)
        if stage == "preparing":
            handle = await guarded(
                partial(
                    gateway.submit,
                    {"parse_job_id": job_id, "filename": filename, "config": snapshot["config"]},
                ),
                timeout=min(30, remaining),
            )
            next_stage = "uploading"
        else:
            if not state_key or not batch_id:
                raise PermanentTaskError("MINERU_SUBMISSION_UNKNOWN", "远端身份缺失，不自动重提")
            handle = store.load_state(state_key)
            if handle.get("batch_id") != batch_id:
                raise PermanentTaskError("MINERU_STATE_UNAVAILABLE", "私有状态身份不符")
            if stage in {"uploading", "remote_waiting", "remote_running", "remote_converting"}:
                observation = await guarded(
                    partial(gateway.poll, handle), timeout=min(30, remaining)
                )
                if observation["state"] == "failed":
                    raise PermanentTaskError("MINERU_PARSE_FAILED", "MinerU明确解析失败，未回退")
                if observation["state"] == "waiting-file":
                    raw = await guarded(
                        partial(LocalFileStorage(settings.upload_path).read, source_key),
                        timeout=min(30, remaining),
                    )
                    if hashlib.sha256(raw).hexdigest() != source_hash:
                        raise PermanentTaskError("SOURCE_HASH_MISMATCH", "原件hash不符")
                    try:
                        await guarded(
                            partial(gateway.upload, raw, handle), timeout=min(120, remaining)
                        )
                    except TransientTaskError:
                        # 应答丢失先查同batch；总预算及任务错误次数仍限制反复上传。
                        raise TransientTaskError(
                            "MINERU_UPLOAD_UNCONFIRMED", "上传未确认，将先查询同batch"
                        ) from None
                    next_stage = "remote_waiting"
                elif observation["state"] == "done":
                    handle["download_url"] = observation["download_url"]
                    next_stage = "downloading"
                else:
                    next_stage = {
                        "pending": "remote_waiting",
                        "running": "remote_running",
                        "converting": "remote_converting",
                    }[observation["state"]]
                delay = 0 if next_stage == "downloading" else snapshot["config"]["poll_interval"]
            elif stage == "downloading":
                raw = await guarded(partial(gateway.download, handle), timeout=min(120, remaining))
                artifact = await guarded(
                    partial(isolated, "package", raw, extension, timeout=min(60, remaining)),
                    timeout=min(60, remaining),
                )
            else:
                raise PermanentTaskError("MINERU_STATE_UNAVAILABLE", "解析检查点无效")
    private_key = None
    if handle is not None:
        private_key = f"{job_id}-{generation}.bin"
        store.save_state(private_key, handle)
    async with factory() as session:
        task, _, document, build = await lock_build_execution(session, task_id, worker, generation)
        job = await session.get(ParseJobModel, job_id)
        if job.cancel_requested_at or job.state in {"succeeded", "failed", "cancelled"}:
            from backend.application.task_execution import ExecutionStopped

            raise ExecutionStopped()
        if job.parse_deadline.replace(tzinfo=timezone.utc) <= utc_now():
            raise PermanentTaskError(
                "MINERU_ATTEMPT_TIMEOUT" if route == "mineru" else "DOCUMENT_PARSE_LIMIT",
                "解析达到截止时间",
            )
        if artifact is not None:
            identity = str(uuid4())
            row = ParsedArtifactModel(
                artifact_id=identity,
                parse_job_id=job_id,
                source_hash=source_hash,
                parser_hash=job.parser_hash,
                protocol=artifact.protocol,
                text=artifact.text,
                text_hash=hashlib.sha256(artifact.text.encode()).hexdigest(),
                manifest_hash=digest(
                    {
                        "source": source_hash,
                        "parser": job.parser_hash,
                        "text": hashlib.sha256(artifact.text.encode()).hexdigest(),
                    }
                ),
                unsupported_json=list(artifact.unsupported),
            )
            session.add(row)
            await session.flush()
            for seq, block in enumerate(artifact.blocks):
                session.add(
                    ParsedBlockModel(
                        block_id=block.block_id,
                        artifact_id=identity,
                        seq=seq,
                        kind=block.kind,
                        text=block.text,
                        start_offset=block.start,
                        end_offset=block.end,
                        heading_path=list(block.heading_path),
                        locations_json=list(block.locations),
                    )
                )
            job.artifact_id, job.state, job.stage = identity, "succeeded", "completed"
            if route == "mineru":
                job.remote_outcome = "completed"
            build.artifact_id, build.stage = identity, "chunk"
        else:
            job.stage, job.state = next_stage, "waiting"
            job.remote_batch_id, job.private_state_key = handle["batch_id"], private_key
            if observation:
                job.poll_count += 1
                job.remote_progress_json = observation.get("progress", {})
                if job.poll_count > snapshot["config"]["max_polls"]:
                    raise PermanentTaskError("MINERU_ATTEMPT_TIMEOUT", "解析轮询达到上限")
            build.state = "waiting"
        await yield_task(session, task, delay=delay)
