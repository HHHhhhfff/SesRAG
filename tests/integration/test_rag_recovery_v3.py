"""本轮独立故障/恢复工程验证；受控假上游不代表MinerU真实效果。"""

import base64
import io
import json
from datetime import timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app import create_app
from backend.application.errors import PermanentTaskError
from backend.application.rag_gc import collect
from backend.application.rag_profiles import import_profiles
from backend.config import Settings
from backend.db.models import TaskModel, utc_now
from backend.db.rag_models import IndexBuildModel, ParseJobModel
from backend.domain.rag import CONSENT_VERSION
from backend.workers.handlers.index_build_handler import process_index_build_task
from backend.workers.runtime import WorkerRuntime


class OfficeGateway:
    submissions = 0
    uploads = 0
    polls = 0
    fail = False
    unknown = False

    def __init__(self, _settings):
        pass

    async def submit(self, job):
        type(self).submissions += 1
        if self.unknown:
            raise PermanentTaskError("MINERU_SUBMISSION_UNKNOWN", "受控未知提交")
        return {
            "batch_id": job["parse_job_id"],
            "upload_url": "https://storage.example/input?private=capability",
        }

    async def upload(self, _raw, _handle):
        type(self).uploads += 1

    async def poll(self, _handle):
        type(self).polls += 1
        if self.fail:
            return {"state": "failed"}
        if not self.uploads:
            return {"state": "waiting-file"}
        if self.polls < 4:
            return {"state": "running"}
        return {
            "state": "done",
            "download_url": "https://storage.example/result?private=capability",
        }

    async def download(self, _handle):
        output = io.BytesIO()
        with ZipFile(output, "w") as archive:
            archive.writestr("full.md", "# 数据库\n\nSesRAG uses PostgreSQL and pgvector.")
        return output.getvalue()


@pytest.fixture
def environment(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'recovery.db'}",
        redis_enabled=False,
        auto_create_schema=True,
        upload_dir=str(tmp_path / "uploads"),
        rag_artifact_dir=str(tmp_path / "artifacts"),
        rag_tmp_dir=str(tmp_path / "tmp"),
        mineru_enabled=True,
        mineru_api_key="controlled-test-only",
        mineru_state_encryption_key=base64.b64encode(b"x" * 32).decode(),
        mineru_storage_host_allowlist="storage.example",
        _env_file=None,
    )
    OfficeGateway.submissions = OfficeGateway.uploads = OfficeGateway.polls = 0
    OfficeGateway.fail = OfficeGateway.unknown = False

    async def handler(*args):
        return await process_index_build_task(*args, gateway_factory=OfficeGateway)

    monkeypatch.setattr("backend.workers.runtime.process_index_build_task", handler)
    app = create_app(settings)
    with TestClient(app) as client:

        async def seed():
            async with app.state.session_factory() as session:
                await import_profiles(
                    session,
                    [
                        {
                            "kind": "parser",
                            "profile_id": "controlled-office",
                            "version": 1,
                            "config": {
                                "parser_kind": "mineru",
                                "formats": [".pdf"],
                                "verified_formats": [".pdf"],
                                "protocol_evidence": "controlled fake only; no real acceptance",
                                "output_protocol": "mineru_cloud_v4_office_text_v1",
                                "poll_interval": 1,
                            },
                        }
                    ],
                )
                await session.commit()

        client.portal.call(seed)
        base = client.get("/api/v3/knowledge-bases").json()["items"][0]["knowledge_base_id"]
        runtime = WorkerRuntime(settings, app.state.session_factory, app.state.notifier)
        yield client, app, runtime, base


def upload(client, base, key="upload"):
    parse = {
        "cloud_consent": True,
        "consent_version": CONSENT_VERSION,
        "parser_profile_id": "controlled-office",
        "parser_profile_version": 1,
    }
    result = client.post(
        "/api/v3/documents",
        data={"knowledge_base_id": base, "parse": json.dumps(parse)},
        files={
            "file": (
                "knowledge.pdf",
                Path("tests/fixtures/rag-v3/knowledge.pdf").read_bytes(),
                "application/pdf",
            )
        },
        headers={"Idempotency-Key": key},
    )
    assert result.status_code in {200, 202}, result.text
    return result.json(), parse


def drive(client, app, runtime, batch, max_steps=16):
    async def advance_clock():
        async with app.state.session_factory() as session:
            tasks = (
                await session.scalars(
                    select(TaskModel).where(
                        TaskModel.state.in_(("waiting_external", "retry_waiting"))
                    )
                )
            ).all()
            for task in tasks:
                task.available_at = utc_now() - timedelta(seconds=1)
            await session.commit()

    for _ in range(max_steps):
        client.portal.call(advance_clock)
        client.portal.call(runtime.run_once)
        result = client.get("/api/v3/index-builds/" + batch).json()
        if result["state"] in {"failed", "succeeded", "cancelled"}:
            return result
    raise AssertionError("有界步骤内未得到终态")


def test_office_resume_waits_do_not_exhaust_error_attempts_and_replay(environment):
    client, app, runtime, base = environment
    document, _ = upload(client, base)
    replayed, _ = upload(client, base)
    assert replayed["document_id"] == document["document_id"]
    state = drive(client, app, runtime, document["latest_build"]["index_batch_id"])
    assert state["state"] == "succeeded", state
    assert OfficeGateway.submissions == 1 and OfficeGateway.uploads == 1

    async def facts():
        async with app.state.session_factory() as session:
            task = await session.get(TaskModel, state["task_id"])
            return task.attempt, task.failure_count

    attempt, failures = client.portal.call(facts)
    assert attempt > 3 and failures == 0
    assert "capability" not in json.dumps(state) and "storage.example" not in json.dumps(state)


def test_unknown_submission_stays_failed_and_requires_new_cost_ack(environment):
    client, app, runtime, base = environment
    OfficeGateway.unknown = True
    document, parse = upload(client, base)
    state = drive(client, app, runtime, document["latest_build"]["index_batch_id"])
    assert state["state"] == "failed" and state["parse"]["remote_outcome"] == "unknown_may_continue"
    for _ in range(3):
        client.portal.call(runtime.run_once)
    assert OfficeGateway.submissions == 1
    retry = client.post(
        f"/api/v3/documents/{document['document_id']}/index-builds",
        json={"parse": parse},
        headers={"Idempotency-Key": "new-operation"},
    )
    assert retry.status_code == 409 and retry.json()["code"] == "MINERU_SUBMISSION_UNKNOWN"


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
def test_submitted_office_stop_reports_remote_may_continue(environment, stop):
    # RAG-014：本机停止不等于云端取消，已申请同batch必须保留远端未知事实。
    client, app, runtime, base = environment
    document, _ = upload(client, base)
    batch = document["latest_build"]["index_batch_id"]
    client.portal.call(runtime.run_once)
    assert OfficeGateway.submissions == 1
    if stop == "cancel":
        state = client.post(f"/api/v3/index-builds/{batch}/cancel").json()
        assert state["state"] == "cancelled"
    else:

        async def expire():
            async with app.state.session_factory() as session:
                build = await session.get(IndexBuildModel, batch)
                job = await session.get(ParseJobModel, build.parse_job_id)
                job.parse_deadline = utc_now() - timedelta(seconds=1)
                await session.commit()

        client.portal.call(expire)
        state = drive(client, app, runtime, batch)
        assert state["state"] == "failed" and state["error_code"] == "MINERU_ATTEMPT_TIMEOUT"
    assert state["parse"]["remote_outcome"] == "unknown_may_continue"
    assert OfficeGateway.submissions == 1
    retried = client.post(
        f"/api/v3/documents/{document['document_id']}/index-builds",
        json={
            "parse": {
                "cloud_consent": True,
                "consent_version": CONSENT_VERSION,
                "parser_profile_id": "controlled-office",
                "parser_profile_version": 1,
            }
        },
        headers={"Idempotency-Key": "after-unknown-stop"},
    )
    assert retried.status_code == 409 and retried.json()["code"] == "MINERU_SUBMISSION_UNKNOWN"


def test_v1_local_text_publishes_explicit_batch_visible_in_v3(environment):
    # RAG-038：保留旧调用契约，但发布身份不能缺失于新工作台和冻结视图。
    client, app, runtime, base = environment
    response = client.post(
        "/api/v1/documents", files={"file": ("legacy.txt", b"PostgreSQL legacy text", "text/plain")}
    )
    assert response.status_code == 201, response.text
    client.portal.call(runtime.run_once)
    current = client.get("/api/v3/documents/" + response.json()["document_id"]).json()
    assert current["availability"] == "ready", current
    assert current["latest_build"]["state"] == "succeeded"
    assert current["latest_build"]["index_batch_id"] == current["active_index_batch_id"]
    diagnostic = client.post(
        "/api/v3/retrieval-executions",
        json={"query": "PostgreSQL", "knowledge_base_id": base},
        headers={"Idempotency-Key": "legacy-through-v3"},
    ).json()
    client.portal.call(runtime.run_once)
    observed = client.get("/api/v3/retrieval-executions/" + diagnostic["execution_id"]).json()
    assert observed["state"] == "succeeded", observed
    evidence = client.get("/api/v3/evidence-bundles/" + observed["bundle_ids"][0]).json()
    assert evidence["text"] == "PostgreSQL legacy text"
    thread = client.post("/api/v1/threads", json={"title": "旧引用保护"}).json()
    run = client.post(
        f"/api/v1/threads/{thread['thread_id']}/messages",
        json={"content": "PostgreSQL"},
        headers={"Idempotency-Key": "legacy-reference"},
    ).json()
    client.portal.call(runtime.run_once)
    assert client.get("/api/v1/runs/" + run["run_id"]).json()["status"] == "succeeded"

    async def protected_reference():
        from backend.db.rag_models import LegacyEvidenceRefModel

        async with app.state.session_factory() as session:
            return await session.scalar(
                select(LegacyEvidenceRefModel.ref_id).where(
                    LegacyEvidenceRefModel.source_message_id.is_not(None)
                )
            )

    assert client.portal.call(protected_reference)


def test_rerank_safety_block_during_embedding_stops_next_external_phase(environment):
    from backend.application.retrieval import execute_retrieval
    from backend.application.retrieval_views import load_scope
    from backend.db.rag_models import RerankProfileModel, RetrievalExecutionModel
    from backend.infrastructure.providers.rag_registry import embedding_from_profile

    client, app, runtime, base = environment
    document, _ = upload(client, base)
    assert (
        drive(client, app, runtime, document["latest_build"]["index_batch_id"])["state"]
        == "succeeded"
    )
    result = client.post(
        "/api/v3/retrieval-executions",
        json={
            "query": "PostgreSQL",
            "knowledge_base_id": base,
            "overrides": {"rerank_enabled": True},
        },
        headers={"Idempotency-Key": "safety-block"},
    ).json()
    calls = []

    async def check():
        async with app.state.session_factory() as session:
            execution = await session.get(RetrievalExecutionModel, result["execution_id"])
            scope = await load_scope(session, app.state.settings, execution.view_id)
            snapshot = execution.snapshot_json

        class Embedding:
            async def embed(self, texts, *, purpose):
                vectors = await embedding_from_profile(snapshot["embedding"]).embed(
                    texts, purpose=purpose
                )
                async with app.state.session_factory() as session:
                    profile = await session.get(RerankProfileModel, ("mock-rerank", 1))
                    profile.security_status = "blocked"
                    await session.commit()
                return vectors

        class Ranker:
            async def rank(self, _query, texts):
                calls.append(True)
                return tuple((i, 0.9) for i in range(len(texts)))

        async def guarded(operation):
            return await operation()

        with pytest.raises(Exception) as error:
            await execute_retrieval(
                app.state.session_factory,
                app.state.settings,
                scope,
                snapshot,
                "PostgreSQL",
                guarded,
                embedding_factory=lambda _: Embedding(),
                rerank_factory=lambda _: Ranker(),
            )
        assert error.value.code == "PROFILE_UNAVAILABLE"

    client.portal.call(check)
    assert not calls


def test_failed_rebuild_and_cancel_preserve_active_and_gc_protects_views(environment):
    client, app, runtime, base = environment
    document, parse = upload(client, base)
    first = document["latest_build"]["index_batch_id"]
    assert drive(client, app, runtime, first)["state"] == "succeeded"
    execution = client.post(
        "/api/v3/retrieval-executions",
        json={"query": "database", "knowledge_base_id": base},
        headers={"Idempotency-Key": "view"},
    ).json()
    client.portal.call(runtime.run_once)
    OfficeGateway.fail = True

    # 增加解析Profile版本，强制云端重新解析而不复用成功产物。
    async def new_parser():
        async with app.state.session_factory() as session:
            source = await session.get(
                ParseJobModel, document["latest_build"]["parse"]["parse_job_id"]
            )
            config = {**source.parser_snapshot["config"], "language": "en"}
            await import_profiles(
                session,
                [
                    {
                        "kind": "parser",
                        "profile_id": "controlled-office",
                        "version": 2,
                        "config": config,
                    }
                ],
            )
            await session.commit()

    client.portal.call(new_parser)
    second = client.post(
        f"/api/v3/documents/{document['document_id']}/index-builds",
        json={"parse": {**parse, "parser_profile_version": 2}},
        headers={"Idempotency-Key": "rebuild"},
    ).json()
    assert drive(client, app, runtime, second["index_batch_id"])["state"] == "failed"
    assert (
        client.get("/api/v3/documents/" + document["document_id"]).json()["active_index_batch_id"]
        == first
    )
    third = client.post(
        f"/api/v3/documents/{document['document_id']}/index-builds",
        json={"parse": parse},
        headers={"Idempotency-Key": "cancel-rebuild"},
    ).json()
    cancelled = client.post("/api/v3/index-builds/" + third["index_batch_id"] + "/cancel")
    assert cancelled.json()["state"] == "cancelled"

    async def cleanup():
        async with app.state.session_factory() as session:
            for build in (await session.scalars(select(IndexBuildModel))).all():
                build.created_at = utc_now() - timedelta(hours=48)
            await session.commit()
        return await collect(app.state.session_factory, app.state.settings, apply=True)

    report = client.portal.call(cleanup)
    assert any(
        r.get("index_batch_id") == first and r["action"] == "protected" for r in report["resources"]
    )
    assert any(
        r.get("index_batch_id") == second["index_batch_id"] and r["action"] == "delete"
        for r in report["resources"]
    )
    assert (
        client.get("/api/v3/retrieval-executions/" + execution["execution_id"]).json()["state"]
        == "succeeded"
    )
