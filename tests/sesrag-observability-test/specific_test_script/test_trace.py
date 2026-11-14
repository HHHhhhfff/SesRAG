"""A07/A08/A10：四类业务任务、真实跨进程protobuf与不可变producer。"""

import asyncio
import json
import time
from pathlib import Path
from uuid import uuid4

from evidence import client, request, spans, wait

from backend.application.rag_profiles import import_profiles
from backend.config import Settings
from backend.db.session import create_engine, create_session_factory


async def profiles():
    engine = create_engine(Settings())
    entries = json.loads(Path("/config/rag-profiles.example.json").read_text())
    async with create_session_factory(engine)() as session:
        await import_profiles(session, entries)
        await session.commit()
    await engine.dispose()


def run():
    asyncio.run(profiles())
    with client() as c:
        base = request(
            c,
            "POST",
            "/api/v3/knowledge-bases",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "name": "004知识库",
                "embedding_profile_id": "mock-embedding",
                "embedding_profile_version": 1,
            },
        )
        docs = []
        for office in (False, True):
            parse = (
                {
                    "parser_profile_id": "mineru-office",
                    "parser_profile_version": 2,
                    "cloud_consent": True,
                    "consent_version": "mineru-office-outbound-v1",
                }
                if office
                else {}
            )
            name = "knowledge.pdf" if office else "knowledge.md"
            content = Path("/tests/rag-fixtures/" + name).read_bytes()
            doc = request(
                c,
                "POST",
                "/api/v3/documents",
                files={"file": (name, content)},
                data={"knowledge_base_id": base["knowledge_base_id"], "parse": json.dumps(parse)},
                headers={"Idempotency-Key": str(uuid4())},
            )
            wait(c, f"/api/v3/documents/{doc['document_id']}", "status")
            docs.append(doc["document_id"])
        # 保留旧文本索引入口，证明第四类任务。
        old = request(
            c, "POST", "/api/v1/documents", files={"file": ("legacy.txt", b"observability sample")}
        )
        for _ in range(300):
            rows = request(c, "GET", "/api/v1/documents")["documents"]
            row = next(r for r in rows if r["document_id"] == old["document_id"])
            if row["status"] in {"indexed", "failed"}:
                assert row["status"] == "indexed"
                break
            time.sleep(0.1)
        else:
            raise AssertionError("旧文本索引超时")
        diagnostic = request(
            c,
            "POST",
            "/api/v3/retrieval-executions",
            json={
                "query": "观测",
                "knowledge_base_id": base["knowledge_base_id"],
                "overrides": {"rerank_enabled": True},
            },
            headers={"Idempotency-Key": str(uuid4())},
        )
        wait(c, "/api/v3/retrieval-executions/" + diagnostic["execution_id"], "state")
        thread = request(c, "POST", "/api/v2/threads", json={"title": "004RAG"})
        key = str(uuid4())
        payload = {
            "branch_id": thread["default_branch_id"],
            "expected_version": 0,
            "content": "OBS_PROMPT_SENTINEL",
            "rag": {
                "enabled": True,
                "knowledge_base_id": base["knowledge_base_id"],
                "overrides": {"rerank_enabled": True},
            },
        }
        created = request(
            c,
            "POST",
            f"/api/v3/threads/{thread['thread_id']}/messages",
            json=payload,
            headers={
                "Idempotency-Key": key,
                "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01",
            },
        )
        replay = request(
            c,
            "POST",
            f"/api/v3/threads/{thread['thread_id']}/messages",
            json=payload,
            headers={"Idempotency-Key": key},
        )
        assert created["task_id"] == replay["task_id"]
        wait(c, "/api/v3/runs/" + created["run_id"])
        assert "run.succeeded" in c.get(f"/api/v3/runs/{created['run_id']}/events/stream").text
    time.sleep(1.2)
    captured = spans()
    assert captured["counts"]["unsafe"] == 0
    data = captured["spans"]
    attempts = [s for s in data if s["name"] == "task.attempt"]
    assert {s["attributes"]["task_kind"] for s in attempts} >= {
        "run",
        "index_document",
        "index_build",
        "retrieval_diagnostic",
    }
    enqueues = {s["span_id"]: s for s in data if s["name"] == "task.enqueue"}
    assert all(a["parent_span_id"] in enqueues for a in attempts)
    assert all(a["trace_id"] == enqueues[a["parent_span_id"]]["trace_id"] for a in attempts)
    assert any(a["attributes"].get("result") == "yielded" for a in attempts)
    assert {s["name"] for s in data} >= {
        "mineru.submit",
        "mineru.upload",
        "mineru.poll",
        "mineru.download",
        "embedding.document",
        "embedding.query",
        "rerank.rank",
        "model.generate",
    }
    assert all(s["events"] == 0 for s in data)
    own = [
        s
        for s in data
        if s["name"] == "task.enqueue" and s["attributes"].get("task_id") == created["task_id"]
    ]
    assert len(own) == 1
    return {
        "task_kinds": sorted({a["attributes"]["task_kind"] for a in attempts}),
        "captured_spans": len(data),
        "trace_topology": "task_sibling_spans_v1",
        "task_id": created["task_id"],
        "document_ids": docs,
    }
