"""生产httpx adapter经真实socket进入正式Runtime；每fixture独立数据库。"""

import socket
import time
from unittest.mock import patch
from uuid import uuid4

import httpx
from pg_document_scenarios import SENTINELS, document, read_index
from pg_harness import until
from pg_network_scenarios import serve
from provider_protocol import ProtocolServer, assert_safe_raw
from sqlalchemy import select

from backend.app import create_app
from backend.db.models import MessageModel, RunEventModel, RunModel, TaskModel
from backend.infrastructure.providers import openai_compatible
from backend.infrastructure.queue import postgres_queue as queue

# 手写独立预期；不得从受测check_status/validate_vector推算结果。
MALFORMED = {
    "embeddings": {
        "non-json": "PROVIDER_INVALID_RESPONSE",
        "missing": "PROVIDER_INVALID_RESPONSE",
        "empty": "PROVIDER_INVALID_RESPONSE",
        "wrong-data": "PROVIDER_INVALID_RESPONSE",
        "missing-embedding": "PROVIDER_INVALID_RESPONSE",
        "wrong-vector": "EMBEDDING_INVALID",
        "383": "EMBEDDING_DIMENSION_MISMATCH",
        "385": "EMBEDDING_DIMENSION_MISMATCH",
        "non-numeric": "EMBEDDING_INVALID",
        "non-finite": "EMBEDDING_INVALID",
        "boolean": "EMBEDDING_INVALID",
        "huge": "EMBEDDING_INVALID",
    },
    "chat/completions": {
        "non-json": "PROVIDER_INVALID_RESPONSE",
        "missing": "PROVIDER_INVALID_RESPONSE",
        "empty": "PROVIDER_EMPTY_CONTENT",
        "wrong-choices": "PROVIDER_INVALID_RESPONSE",
        "wrong-delta": "PROVIDER_INVALID_RESPONSE",
        "wrong-content": "PROVIDER_INVALID_RESPONSE",
        "missing-content": "PROVIDER_EMPTY_CONTENT",
        "empty-content": "PROVIDER_EMPTY_CONTENT",
        "missing-done": "PROVIDER_INVALID_RESPONSE",
    },
}


def configure(h, base):
    # 通过正式Settings重新校验，不绕过组合边界；API快照和Worker使用同配置。
    from backend.config import Settings

    h.cfg = Settings(
        _env_file=None,
        **{
            **h.cfg.model_dump(),
            "mock_provider": False,
            "model_base_url": base,
            "model_api_key": "virtual-secret-5b",
            "model_name": "fixture-model",
            "embedding_model_name": "fixture-embedding",
            "task_retry_base_delay": 1,
        },
    )


async def raw_safety(h, ids):
    async with h.factory() as session:
        task = await session.get(TaskModel, ids["task_id"])
        values = [task.last_error_code, task.progress_json]
        if "run_id" in ids:
            run = await session.get(RunModel, ids["run_id"])
            messages = list(
                await session.scalars(
                    select(MessageModel).where(MessageModel.thread_id == ids["thread_id"])
                )
            )
            events = list(
                await session.scalars(
                    select(RunEventModel).where(RunEventModel.run_id == ids["run_id"])
                )
            )
            values += [
                run.snapshot_json,
                run.last_error_code,
                [m.content for m in messages],
                [m.citations_json for m in messages],
                [e.payload_json for e in events],
            ]
    app = create_app(h.cfg)
    async with serve(app) as base, httpx.AsyncClient() as client:
        routes = (
            [
                "/api/v1/runs/" + ids["run_id"],
                "/api/v1/threads/" + ids["thread_id"],
                "/api/v1/runs/" + ids["run_id"] + "/events",
            ]
            if "run_id" in ids
            else ["/api/v1/documents"]
        )
        for route in routes:
            response = await client.get(base + route)
            assert response.status_code == 200
            values.append(response.text)
    h.check(
        assert_safe_raw(values + h.logs.raw, SENTINELS),
        "原始正式HTTP/Message/Event/Task/snapshot/默认Runtime日志在Context脱敏前无哨兵",
    )
    h.trace["raw_safety"] = {
        "checked_before_context_redaction": True,
        "channels": ["http", "message", "event", "task", "snapshot", "runtime-log"],
        "leaked": False,
    }


async def protocol_failure(h, endpoint, mode, kind="run"):
    token = uuid4().hex[:8]
    server = ProtocolServer(token, endpoint=endpoint, mode=mode)
    expected = (
        "PROVIDER_HTTP_" + mode.removeprefix("status-")
        if mode.startswith("status-")
        else "PROVIDER_TIMEOUT"
        if mode == "timeout"
        else "PROVIDER_TRANSPORT_ERROR"
        if mode in ("socket", "refused")
        else MALFORMED[endpoint][mode]
    )
    transient = mode in (
        "status-408",
        "status-429",
        "status-500",
        "status-503",
        "timeout",
        "socket",
        "refused",
    )
    async with server.serve() as base:
        refused_base = None
        if mode == "refused":
            # 预先绑定但不listen的本例端口，避免意外命中宿主其他服务。
            refusal = socket.socket()
            refusal.bind(("127.0.0.1", 0))
            refused_base = f"http://127.0.0.1:{refusal.getsockname()[1]}/{token}/v1"
            if endpoint == "embeddings":
                base = refused_base
        configure(h, base)
        ids = await h.seed() if kind == "run" else await document(h)
        worker = h.worker()
        if mode == "refused" and endpoint == "chat/completions":
            # 每次attempt的embedding保持真实成功，只有模型Port使用确知未listen的本例端口。
            def factory(snapshot):
                provider = openai_compatible.OpenAICompatibleProvider
                return (
                    provider(base, "virtual-secret-5b", "fixture-model", "fixture-embedding"),
                    provider(
                        refused_base, "virtual-secret-5b", "fixture-model", "fixture-embedding"
                    ),
                )

            worker.provider_factory = factory
        try:
            # 缩短测试总预算但保留真实TCP计时与生产asyncio/httpx超时处理。
            with patch.object(
                openai_compatible, "PROVIDER_TIMEOUT", 0.25 if mode == "timeout" else 10
            ):
                for attempt in range(1, 4 if transient else 2):
                    started = time.monotonic()
                    await worker.run_once()
                    facts = await h.facts(ids)
                    h.check(
                        facts["task"]["attempt"] == attempt
                        and facts["task"]["last_error_code"] == expected,
                        f"{endpoint}/{mode}/{kind}attempt{attempt}实际协议错误稳定分类{expected}",
                    )
                    if transient and attempt < 3:
                        h.check(
                            facts["task"]["state"] == "retry_waiting"
                            and facts["task"]["available_at"] > queue.utc_now(),
                            f"{mode}attempt{attempt}持久未来退避",
                        )
                        h.check(not await worker.run_once(), f"{mode}available_at前不重复调用")

                        async def due(facts=facts):
                            return queue.utc_now() >= facts["task"]["available_at"]

                        await until(due, 6)
                    if mode == "timeout":
                        h.check(time.monotonic() - started >= 0.20, "实际网络挂起触发有界生产超时")
        finally:
            if mode == "refused":
                refusal.close()
        final = await h.facts(ids)
        h.check(
            final["task"]["state"] == "failed"
            and final["task"]["attempt"] == (3 if transient else 1),
            f"{mode}/{kind}有限尝试后正式Task failed",
        )
        if kind == "run":
            h.check(
                final["run"]["status"] == "failed"
                and final["run"]["last_error_code"] == expected
                and final["run"]["assistant_message_id"] is None
                and len(final["messages"]) == 1,
                f"{mode}Run/Task一致失败，无伪成功assistant",
            )
            h.check(
                [e["type"] for e in final["events"]].count("run.failed") == 1
                and not any(e["type"] == "run.succeeded" for e in final["events"]),
                f"{mode}唯一失败终态Event",
            )
        else:
            final = await read_index(h, ids)
            h.check(
                final["document"]["status"] == "failed"
                and final["document"]["error"] == expected
                and not final["chunks"]
                and final["document"]["active"] is None,
                f"{mode}Document/Task失败且无错维候选发布",
            )
        await raw_safety(h, ids)
        targeted = [c for c in server.calls if c["endpoint"] == endpoint]
        if mode != "refused":
            h.check(
                len(targeted) == (3 if transient else 1),
                f"{mode}实际HTTP调用次数匹配attempt，不盲重试",
            )
            h.check(
                all(
                    c["model"]
                    == ("fixture-embedding" if endpoint == "embeddings" else "fixture-model")
                    for c in targeted
                ),
                "实际HTTP使用配置模型",
            )
        h.check(not await worker.run_once(), f"{mode}终态之后不再领取执行")
        h.trace.update(
            protocol=server.calls,
            fixture={
                "endpoint": endpoint,
                "mode": mode,
                "kind": kind,
                "expected_code": expected,
                "transient": transient,
            },
        )
    h.check(server.closed, "协议listener/连接/协程finally实际关闭")


async def three_fragments(h):
    gates = [h.gate() for _ in range(3)]
    server = ProtocolServer(
        uuid4().hex[:8],
        endpoint="chat/completions",
        mode="three",
        gate=lambda index: gates[index].pause(),
    )
    async with server.serve() as base:
        configure(h, base)
        ids = await h.seed()
        work = h.launch(h.worker().run_once())
        for index, gate in enumerate(gates):
            await gate.wait()

            async def persisted(index=index):
                facts = await h.facts(ids)
                return (
                    facts
                    if sum(e["type"] == "answer.delta" for e in facts["events"]) == index + 1
                    else None
                )

            facts = await until(persisted)
            h.check(
                facts["run"]["status"] == "running" and not server.finished and not work.done(),
                f"第{index + 1}片真实HTTP尚未结束时已独立PG持久Journal",
            )
            h.trace.setdefault("persisted_fragments", []).append(
                {
                    "index": index + 1,
                    "at": time.monotonic(),
                    "seq": facts["events"][-1]["seq"],
                    "http_finished": server.finished,
                }
            )
            gate.open()
        await work
        facts = await h.facts(ids)
        async with h.factory() as session:
            message = await session.get(MessageModel, facts["run"]["assistant_message_id"])
            h.check(message.content == "第一片第二片第三片", "三片按顺序组成唯一最终assistant正文")
        h.check(
            facts["run"]["status"] == "succeeded"
            and server.finished
            and server.calls[-1]["stream"] is True,
            "真实stream=true及DONE之后Run成功",
        )
        h.trace.update(protocol=server.calls, fragments=server.fragments)
    h.check(server.closed, "三片协议listener/连接/协程finally关闭")


async def valid_index(h):
    server = ProtocolServer(uuid4().hex[:8])
    async with server.serve() as base:
        configure(h, base)
        ids = await document(h)
        await h.worker().run_once()
        facts = await read_index(h, ids)
        h.check(
            facts["task"]["state"] == "succeeded"
            and facts["document"]["status"] == "indexed"
            and len(facts["chunks"]) == 1
            and facts["hits"][0]["batch"] == facts["document"]["active"],
            "真实HTTP384维对照Task/Document成功且active可检索",
        )
        h.check(
            len(server.calls) == 1 and server.calls[0]["model"] == "fixture-embedding",
            "384维对照确实消费生产HTTP embedding协议",
        )
        h.trace["protocol"] = server.calls
    h.check(server.closed, "384维协议服务finally关闭")


provider_scenarios = {
    "provider-three-fragments": three_fragments,
    "provider-index-valid": valid_index,
}
for endpoint, short in (("embeddings", "embed"), ("chat/completions", "chat")):
    for mode in [
        "status-400",
        "status-401",
        "status-403",
        "status-404",
        "status-408",
        "status-429",
        "status-500",
        "status-503",
        "timeout",
        "socket",
        "refused",
        *MALFORMED[endpoint],
    ]:
        provider_scenarios[f"provider-{short}-{mode}"] = lambda h, endpoint=endpoint, mode=mode: (
            protocol_failure(h, endpoint, mode)
        )
for mode in ("383", "385", "status-400", "status-500"):
    provider_scenarios[f"provider-index-{mode}"] = lambda h, mode=mode: protocol_failure(
        h, "embeddings", mode, "index"
    )
