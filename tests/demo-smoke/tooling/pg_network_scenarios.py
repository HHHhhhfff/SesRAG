"""真实HTTP/SSE、冻结Provider配置及Linux main持锁退出专项。"""

import asyncio
import importlib.util
import json
import signal
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pg_harness import ChildWorker, Provider, until
from sqlalchemy import select

from backend.app import create_app
from backend.db.models import TaskModel
from backend.infrastructure.events.journal import append_event
from backend.infrastructure.queue import postgres_queue as queue
from backend.infrastructure.rag.pgvector_store import PgVectorStore


@asynccontextmanager
async def serve(app):
    # 随机loopback端口，服务任务在已登记测试容器内，退出必关闭socket。
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    worker = asyncio.create_task(server.serve(sockets=[sock]))
    try:

        async def started():
            return server.started

        await until(started)
        yield "http://127.0.0.1:" + str(sock.getsockname()[1])
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(worker, 5)
        finally:
            sock.close()


async def frames(client, url, maximum=None, seen=None):
    result = []
    async with asyncio.timeout(12):
        async with client.stream("GET", url) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            fields = {}
            async for line in response.aiter_lines():
                if not line:
                    if "data" in fields:
                        value = json.loads(fields["data"])
                        assert (
                            fields["id"] == str(value["seq"]) and fields["event"] == value["type"]
                        )
                        result.append(value)
                        if seen:
                            await seen(value)
                        if maximum and len(result) >= maximum:
                            return result
                    fields = {}
                elif ":" in line:
                    key, value = line.split(":", 1)
                    fields[key] = value.lstrip()
    return result


async def sse_boundary(h):
    import backend.api.routes.runs as routes

    ids = await h.seed()
    gate = h.gate()
    original = routes.get_run_events
    captured = False

    async def read_barrier(session, settings, run_id, cursor):
        nonlocal captured
        events = await original(session, settings, run_id, cursor)
        if run_id == ids["run_id"] and not captured:
            captured = True
            await gate.pause()
        return events

    async def append(label):
        async with h.factory() as session:
            await append_event(session, ids["run_id"], "answer.delta", {"text": label})
            await session.commit()

    app = create_app(h.cfg)
    async with serve(app) as base, httpx.AsyncClient() as client:
        with patch.object(routes, "get_run_events", read_barrier):
            delivered = asyncio.Event()

            async def observed(frame):
                if frame["seq"] == 3:
                    delivered.set()

            pending = h.launch(
                frames(
                    client,
                    base + "/api/v1/runs/" + ids["run_id"] + "/events/stream?after_seq=1",
                    seen=observed,
                )
            )
            await gate.wait()
            await append("历史读取后交付前")
            gate.open()
            await asyncio.wait_for(delivered.wait(), 5)
            await append("流建立后")
            response = await client.post(base + "/api/v1/runs/" + ids["run_id"] + "/cancel")
            h.check(response.status_code == 200, "正式网络cancel提交终态")
            observed_frames = await pending
    facts = await h.facts(ids)
    h.check(
        [f["seq"] for f in observed_frames] == [e["seq"] for e in facts["events"] if e["seq"] > 1],
        "真实SSE历史前/读后交付前/建立后三段完整交付，无缺口重复",
    )
    h.check([f["seq"] for f in observed_frames] == [2, 3, 4, 5], "独立手定边界序列2/3/4/5全部收到")
    h.trace["frames"] = [{"seq": f["seq"], "type": f["type"]} for f in observed_frames]


async def sse_disconnect(h):
    ids = await h.seed()
    gate = h.gate()
    provider = Provider(stage="delta", gate=gate)
    pending = h.launch(h.worker(provider).run_once())
    await gate.wait()
    before = await h.facts(ids)
    first_seq = next(e["seq"] for e in before["events"] if e["type"] == "answer.delta")
    app = create_app(h.cfg)
    async with serve(app) as base, httpx.AsyncClient() as client:
        url = base + "/api/v1/runs/" + ids["run_id"] + "/events/stream"
        disconnected = await frames(client, url, maximum=first_seq)
        h.check(
            disconnected[-1]["type"] == "answer.delta"
            and (await h.facts(ids))["run"]["status"] == "running",
            "真实socket客户端首delta后关闭时Run仍running",
        )
        h.check(
            (await h.facts(ids))["run"]["cancel_requested_at"] is None, "断开客户端没有提交取消"
        )
        gate.open()
        await pending
        replay = await frames(client, url + "?after_seq=" + str(first_seq))
    facts = await h.facts(ids)
    h.check(
        facts["run"]["status"] == "succeeded" and facts["run"]["cancel_requested_at"] is None,
        "断流不取消，原Run/Task继续成功",
    )
    h.check(
        [f["seq"] for f in replay] == [e["seq"] for e in facts["events"] if e["seq"] > first_seq],
        "新socket完整补放最后已收seq之后的持久后缀",
    )
    h.check(
        sum(e["type"] == "answer.delta" for e in facts["events"]) == 3
        and len(facts["messages"]) == 2,
        "三片持久增量完整且唯一assistant",
    )


async def sse_failed(h):
    ids = await h.seed()
    await h.worker(Provider(failures=1, permanent=True)).run_once()
    app = create_app(h.cfg)
    async with serve(app) as base, httpx.AsyncClient() as client:
        url = base + "/api/v1/runs/" + ids["run_id"] + "/events/stream"
        events = await frames(client, url)
        empty = await frames(client, url + "?after_seq=" + str(events[-1]["seq"]))
    h.check(
        events[-1]["type"] == "run.failed"
        and sum(
            f["type"].startswith("run.")
            and f["type"] in {"run.succeeded", "run.failed", "run.cancelled"}
            for f in events
        )
        == 1,
        "真实failed Run网络流只有一个终态并正常EOF",
    )
    h.check(empty == [], "失败终态空后缀也正常EOF")


async def snapshot(h):
    protocol = FastAPI()
    trace = []

    @protocol.post("/v1/embeddings")
    async def embedding(request: Request):
        body = await request.json()
        trace.append({"endpoint": "embeddings", "model": body["model"]})
        return {"data": [{"embedding": [1.0] + [0.0] * 383}]}

    @protocol.post("/v1/chat/completions")
    async def chat(request: Request):
        body = await request.json()
        trace.append({"endpoint": "chat", "model": body["model"], "stream": body.get("stream")})

        async def stream():
            yield (
                "data: "
                + json.dumps({"choices": [{"delta": {"content": "冻结模型回答"}}]})
                + "\n\n"
            )
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    queries = []

    class Store(PgVectorStore):
        async def search(self, owner, vector, top_k):
            queries.append({"owner": owner, "top_k": top_k})
            return await super().search(owner, vector, top_k)

    async with serve(protocol) as base:
        create_cfg = h.cfg.model_copy(
            update={
                "mock_provider": False,
                "model_name": "model-A",
                "embedding_model_name": "embed-A",
                "model_api_key": "fake-test-key",
                "model_base_url": base + "/v1",
                "rag_top_k": 1,
            }
        )
        app = create_app(create_cfg)
        async with serve(app) as api, httpx.AsyncClient() as client:
            thread = (await client.post(api + "/api/v1/threads", json={"title": "冻结配置"})).json()
            response = await client.post(
                api + "/api/v1/threads/" + thread["thread_id"] + "/messages",
                json={"content": "安全问题"},
            )
            h.check(response.status_code == 201, "非Mock配置通过正式HTTP创建Run")
            ids = {**response.json(), "thread_id": thread["thread_id"]}
        before = (await h.facts(ids))["run"]["snapshot_json"]
        h.cfg.mock_provider = False
        h.cfg.model_name, h.cfg.embedding_model_name = "model-B", "embed-B"
        h.cfg.model_base_url, h.cfg.model_api_key, h.cfg.rag_top_k = (
            base + "/v1",
            "fake-test-key",
            3,
        )
        await h.worker(vector_store_factory=Store).run_once()
    facts = await h.facts(ids)
    h.check(
        before == facts["run"]["snapshot_json"]
        and before["model"] == "model-A"
        and before["retrieval"]["top_k"] == 1
        and "fake-test-key" not in json.dumps(before),
        "非Mock快照冻结model-A/top_k1且无Key并执行后不变",
    )
    h.check(
        trace
        == [
            {"endpoint": "embeddings", "model": "embed-A"},
            {"endpoint": "chat", "model": "model-A", "stream": True},
        ],
        "真实OpenAI-compatible HTTP请求消费创建时embedding/model且stream=true",
    )
    h.check(
        queries == [{"owner": create_cfg.owner_id, "top_k": 1}]
        and facts["run"]["status"] == "succeeded",
        "改变Worker为model-B/top_k3后实际检索仍消费冻结top_k1并成功",
    )
    h.trace.update(protocol=trace, search=queries)


async def final_publication(h):
    import io
    from contextlib import redirect_stdout

    spec = importlib.util.spec_from_file_location(
        "execution_probe", Path(__file__).parents[2] / "integration" / "execution_pg_probe.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = io.StringIO()
    with redirect_stdout(captured):
        await module.final_publication_probe(h.engine, h.factory, h.cfg)
    print(captured.getvalue(), end="")
    rows = [
        json.loads(line.removeprefix("FINAL_PUBLICATION:"))
        for line in captured.getvalue().splitlines()
        if line.startswith("FINAL_PUBLICATION:")
    ]
    h.check(len(rows) == 4, "最终发布四个独立真实PG组合全部执行")
    for row in rows:
        h.check(
            row["outcome"] == "rejected" and row["before"] == row["after"],
            f"{row['stage']}/{row['expiry']}最终flush后过期整组事实及两游标回滚",
        )
    h.trace["publication"] = rows
    # 最终授权时间边界直接消费真实判定；不可把commit网络时长冒充零延迟。
    from datetime import timedelta

    from backend.application.task_execution import ExecutionStopped, check_locked_times

    now = queue.utc_now()
    with patch.object(queue, "utc_now", return_value=now):
        check_locked_times(now + timedelta(microseconds=1), now + timedelta(microseconds=1))
        for lease, deadline in (
            (now, now + timedelta(seconds=1)),
            (now + timedelta(seconds=1), now),
        ):
            try:
                check_locked_times(lease, deadline)
            except ExecutionStopped:
                continue
            raise AssertionError("最终授权等号未拒绝")
    h.check(True, "最终授权边界lease/deadline等号拒绝、严格未来接受")


async def signal_locks(h):
    h.cfg.worker_shutdown_grace = 1
    for phase in ("claim", "release"):
        ids = await h.seed()
        async with h.factory() as blocker:
            if phase == "claim":
                await queue.lock_run(blocker, ids["run_id"])
            child = ChildWorker(h)
            if phase == "release":
                await child.reached()
                await queue.lock_run(blocker, ids["run_id"])
            else:
                await h.locked()
            stopped = time.monotonic()
            child.signal(signal.SIGTERM)
            code = await child.wait_exit(5)
            elapsed = time.monotonic() - stopped
            h.check(code == 0 and elapsed < 4, f"生产main在PG {phase}锁等待中真实SIGTERM有界exit0")
            async with h.factory() as observer:
                task = (
                    await observer.execute(
                        select(TaskModel)
                        .where(TaskModel.task_id == ids["task_id"])
                        .with_for_update(nowait=True)
                    )
                ).scalar_one()
                lease = task.lease_expires_at
            await asyncio.sleep(1.2)
            h.check(
                (await h.facts(ids))["task"]["lease_expires_at"] == lease,
                f"{phase}退出后Task锁已释放且无迟到续租",
            )
            h.trace.setdefault("processes", []).append(
                {
                    "phase": phase,
                    "pid": child.process.pid,
                    "exit_code": code,
                    "elapsed": elapsed,
                    "logs": child.logs(),
                }
            )
        await h.cancel(ids)


async def signal_production_provider(h):
    protocol = FastAPI()
    gate = h.gate()

    @protocol.post("/v1/embeddings")
    async def embed(request: Request):
        body = await request.json()
        h.check(body["model"] == "real-embedding", "真实生产Provider已发出HTTP embedding请求")
        await gate.pause()
        return {"data": [{"embedding": [1.0] + [0.0] * 383}]}

    async with serve(protocol) as base:
        h.cfg.mock_provider = False
        h.cfg.model_base_url = base + "/v1"
        h.cfg.model_api_key = "fake-key"
        h.cfg.model_name = "real-model"
        h.cfg.embedding_model_name = "real-embedding"
        h.cfg.worker_shutdown_grace = 1
        ids = await h.seed()
        child = ChildWorker(h, "production")
        try:
            await gate.wait()
            started = time.monotonic()
            child.signal(signal.SIGTERM)
            code = await child.wait_exit(5)
            elapsed = time.monotonic() - started
            h.check(
                code == 0 and elapsed < 4,
                "生产main实际OpenAI-compatible httpx挂起中SIGTERM正常取消并有界exit0",
            )
            after = await h.facts(ids)
            h.check(
                after["task"]["state"] == "retry_waiting"
                and after["run"]["status"] == "retry_waiting",
                "取消真实HTTP调用后正式release保留原Run/Task可恢复",
            )
            await asyncio.sleep(1.2)
            h.check(await h.facts(ids) == after, "main退出后真实Provider不产生迟到事实或续租")
            h.trace.update(
                pid=child.process.pid, exit_code=code, elapsed=elapsed, logs=child.logs()
            )
        finally:
            gate.open()


network_scenarios = {
    "signal-production-provider": signal_production_provider,
    "sse-boundary": sse_boundary,
    "sse-disconnect": sse_disconnect,
    "sse-failed": sse_failed,
    "snapshot": snapshot,
    "final-publication": final_publication,
    "signal-locks": signal_locks,
}
