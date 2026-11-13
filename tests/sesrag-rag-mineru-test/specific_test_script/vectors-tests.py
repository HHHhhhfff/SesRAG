"""VEC本地协议及IDX候选/发布；真实计数阻断项由real-business登记。"""

import asyncio
import copy
import json
import math
import struct
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import httpx
from helpers.case_runner import run_category
from helpers.common import SUITE, load

from backend.application.vector_validation import normalize_l2_float32, validate_vector
from backend.domain.rag import EmbeddingSpace
from backend.domain.rag_profiles import EmbeddingConfig
from backend.infrastructure.providers.bailian_embedding import BailianEmbedding


def protocol(c, body, texts=("a", "b", "c"), status=200, **changes):
    # 真实适配器+受控HTTP只证明协议，不启用业务verified Profile。
    config = copy.deepcopy(
        next(
            r["config"]
            for r in load(SUITE / "fixtures/profiles.real.example.json")
            if r["profile_id"] == "bailian-embedding"
        )
    )
    config.update(changes)
    observed = []

    def respond(request):
        observed.append(json.loads(request.content))
        return httpx.Response(status, json=body)

    provider = BailianEmbedding(
        EmbeddingConfig.model_validate(config),
        "dummy-protocol-only",
        transport=httpx.MockTransport(respond),
    )
    vectors = asyncio.run(provider.embed(texts))
    c.note(
        "执行",
        {"证据层": "协议模拟", "调用数": len(observed), "维度": len(vectors[0]) if vectors else 0},
    )
    return vectors, observed, provider


def vec001(c):
    # VEC_001：通用空间与真实适配维度契约分开。
    for dimension in (1, 384, 1024, 2000):
        c.equal(
            EmbeddingSpace(model="x", revision="r", dimension=dimension).dimension,
            dimension,
            "通用支持维度",
        )
    for dimension in (0, 2001):
        c.rejects(
            lambda dimension=dimension: EmbeddingSpace(
                model="x", revision="r", dimension=dimension
            ),
            error_types=(ValueError,),
        )
    config = copy.deepcopy(
        next(
            r["config"]
            for r in load(SUITE / "fixtures/profiles.real.example.json")
            if r["profile_id"] == "bailian-embedding"
        )
    )
    for dimension in (384, 2000):
        config["space"]["dimension"] = dimension
        c.rejects(lambda: EmbeddingConfig.model_validate(config), error_types=(ValueError,))


def vec002(c):
    # VEC_002：乱序index恢复及缺/重/多/非整数身份拒绝。
    # 非共线单位基向量，归一化也可独立识别；数量正确但排序错误必须失败。
    rows = [{"index": i, "embedding": [float(j == i) for j in range(1024)]} for i in range(3)]
    vectors, observed, _ = protocol(c, {"data": list(reversed(rows))})
    c.equal(len(vectors), 3, "乱序恢复原数量")
    for i, vector in enumerate(vectors):
        c.equal(list(vector), rows[i]["embedding"], "响应index逐输入还原向量：" + str(i))
    for value in (
        rows[:2],
        rows + [rows[0]],
        [rows[0], rows[0], rows[2]],
        [{**rows[0], "index": 0.0}, *rows[1:]],
        [rows[0], rows[1], {**rows[2], "index": 5}],
    ):
        c.rejects(
            lambda value=value: protocol(c, {"data": value}), codes={"EMBEDDING_PROTOCOL_INVALID"}
        )
    c.equal(observed[0]["input"], ["a", "b", "c"], "向量输入顺序原样发送")


def vec003(c):
    # VEC_003：数值/维度/float32下溢，不能默认为空命中。
    for vector in (
        [0, 0],
        [math.nan, 1],
        [math.inf, 1],
        [1e40, 1],
        ["1", 2],
        [True, 1],
        [1e-100, 0],
        [1],
    ):
        c.rejects(lambda vector=vector: validate_vector(vector, dimension=2))
    c.equal(validate_vector([1, 2], dimension=2), [1.0, 2.0], "有效向量可用")


def vec004(c):
    # VEC_004：独立math/struct参考，document与query请求对称。
    for dimension in (384, 1024):
        vector = [float(i % 7 + 1) for i in range(dimension)]
        norm = math.sqrt(sum(v * v for v in vector))
        expected = [struct.unpack("<f", struct.pack("<f", v / norm))[0] for v in vector]
        c.equal(
            normalize_l2_float32(vector, dimension=dimension), expected, "归一化到实际float32精度"
        )
    body = {"data": [{"index": 0, "embedding": [1.0] * 1024}]}
    _, _, provider = protocol(c, body, texts=("same",))
    c.equal(
        asyncio.run(provider.embed(("same",), purpose="document")),
        asyncio.run(provider.embed(("same",), purpose="query")),
        "文档/查询相同归一化",
    )


def vec005(c):
    # VEC_005：批16/17与输入字节界，拒绝前调用数为0。
    for texts in (tuple("x" for _ in range(17)), ("",), (" ",), ("x" * 8193,)):
        c.rejects(lambda texts=texts: protocol(c, {}, texts=texts), codes={"EMBEDDING_INPUT_LIMIT"})
    for texts in (tuple("x" for _ in range(16)), ("x" * 8192,)):
        body = {"data": [{"index": i, "embedding": [1.0] * 1024} for i in range(len(texts))]}
        c.equal(len(protocol(c, body, texts=texts)[0]), len(texts), "合法批量/输入边界")


def vec006(c):
    # VEC_006：冻结用途为identity，query不加前缀、不跟随生成模型。
    body = {"data": [{"index": 0, "embedding": [1.0] * 1024}]}
    _, requests, provider = protocol(c, body, texts=(" 原文🙂 ",))
    asyncio.run(provider.embed((" 原文🙂 ",), purpose="query"))
    c.equal(requests[0], requests[1], "两用途完全同一冻结映射")
    c.equal(set(requests[0]), {"model", "input", "dimensions", "encoding_format"}, "不擅加厂商字段")


def vec007(c):
    # VEC_007：外部故障不切Mock/不伪空。
    for status, code in (
        (401, "EMBEDDING_SERVICE_FAILED"),
        (403, "EMBEDDING_SERVICE_FAILED"),
        (429, "EMBEDDING_TEMPORARY_UNAVAILABLE"),
        (503, "EMBEDDING_TEMPORARY_UNAVAILABLE"),
    ):
        c.rejects(lambda status=status: protocol(c, {}, status=status), codes={code})
    c.rejects(lambda: protocol(c, {"data": "bad"}), codes={"EMBEDDING_PROTOCOL_INVALID"})
    e = c.environment()
    doc = e.upload(finish=False)
    build = e.to_stage(doc, "embed")
    e.plan(e.next_scope(build["task_id"]), "embedding", [{"fault": "bad_vector"}])
    result = e.finish("/api/v3/index-builds/" + build["index_batch_id"], successful=False)
    c.equal(result["state"], "failed", "坏向量无法发布")


def vec008(c):
    # VEC_008：只破坏候选，实际PG拒绝空间/维度/来源伪造。
    e = c.environment()
    doc = e.upload(finish=False)
    e.to_stage(doc, "embed")
    for change in ("space_id='forged'", "dimension=1024", "legacy_unverified=true"):
        c.rejects(lambda change=change: e.sql("UPDATE chunks SET " + change))
    c.rejects(lambda: e.sql("UPDATE chunks SET embedding='[1,2]'::vector"))
    for provenance in ('legacy_unknown', 'legacy_confirmed', 'legacy_verified'):
        c.rejects(lambda provenance=provenance: e.sql(
            "UPDATE index_builds SET provenance=:p", {'p': provenance}))


def idx001(c):
    # IDX_001：构建登记后的冻结快照不受新版默认影响。
    e = c.environment()
    doc = e.upload(finish=False)
    before = e.sql("SELECT embedding_snapshot,chunker_snapshot FROM index_builds")[0]
    profile = copy.deepcopy(load(SUITE / "fixtures/profiles.local.json")[0])
    profile["version"] = 2
    profile["config"]["space"]["revision"] = "new-default"
    e.import_profiles([profile])
    e.finish("/api/v3/index-builds/" + doc["latest_build"]["index_batch_id"])
    c.equal(
        e.sql("SELECT embedding_snapshot,chunker_snapshot FROM index_builds")[0],
        before,
        "原快照固定",
    )


def idx002(c):
    # IDX_002：parse/chunk/embed/publish每阶段候选不可召回。
    e = c.environment()
    doc = e.upload(finish=False)
    for stage in ("parse", "chunk", "embed", "publish"):
        e.to_stage(doc, stage)
        current = e.request("GET", "/api/v3/documents/" + doc["document_id"])
        c.equal(current["active_index_batch_id"], None, "候选阶段不切active：" + stage)
        c.equal(e.diagnostic()["mode"], "empty", "候选不进入冻结View：" + stage)
    e.finish("/api/v3/index-builds/" + doc["latest_build"]["index_batch_id"])


def idx003(c):
    # IDX_003：发布manifest/active/Task/scope revision同事务一致。
    e = c.environment()
    revision = e.sql("SELECT scope_revision FROM knowledge_bases")[0]["scope_revision"]
    doc = e.upload(raw=("fact\n" * 400).encode())
    rows = e.sql(
        (
            "SELECT b.state,b.chunk_count,b.manifest_hash,t.state AS task_stat"
            "e,d.active_index_batch_id,k.scope_revision FROM index_builds b JO"
            "IN tasks t ON t.task_id=b.task_id JOIN documents d ON d.document_"
            "id=b.document_id JOIN knowledge_bases k ON k.knowledge_base_id=b."
            "knowledge_base_id"
        )
    )
    row = rows[0]
    c.equal(
        (row["state"], row["task_state"], row["active_index_batch_id"]),
        ("succeeded", "succeeded", doc["active_index_batch_id"]),
        "所有成功事实一致",
    )
    c.equal(row["scope_revision"], revision + 1, "发布推进范围修订")
    c.equal(len(row["manifest_hash"]), 64, "完整manifest有hash")
    c.equal(e.sql("SELECT count(*) n FROM chunks")[0]["n"], row["chunk_count"], "发布片数完整")


def idx004(c):
    # IDX_004：每种候选损坏独立新Build，不能污染已发布批次。
    e = c.environment()
    for change in ("delete", "seq", "hash", "vector"):
        doc = e.upload(finish=False)
        build = e.to_stage(doc, "publish")
        parameters = {"id": build["index_batch_id"]}
        query = {
            "delete": "DELETE FROM chunks",
            "seq": "UPDATE chunks SET seq=10",
            "hash": "UPDATE chunks SET content_hash='bad'",
            "vector": "UPDATE chunks SET embedding=NULL",
        }[change]
        e.sql(query + " WHERE index_batch_id=:id", parameters)
        result = e.finish("/api/v3/index-builds/" + build["index_batch_id"], successful=False)
        c.equal(result["error_code"], "INDEX_MANIFEST_INVALID", "候选损坏拒绝发布：" + change)
        c.equal(
            e.request("GET", "/api/v3/documents/" + doc["document_id"])["active_index_batch_id"],
            None,
            "无半发布",
        )


def idx005(c):
    # IDX_005：失败/取消/截止保留旧active，latest保留新尝试。
    e = c.environment()
    doc = e.upload()
    for mode in ("failure", "cancel", "deadline"):
        build = e.request(
            "POST",
            "/api/v3/documents/" + doc["document_id"] + "/index-builds",
            expected=(202,),
            json={},
            headers={"Idempotency-Key": str(uuid4())},
        )
        if mode == "cancel":
            e.request(
                "POST",
                "/api/v3/index-builds/" + build["index_batch_id"] + "/cancel",
                expected=(200, 202),
            )
        elif mode == "deadline":
            e.sql(
                "UPDATE tasks SET deadline_at=now()-interval '1 second' WHERE task_id=:id",
                {"id": build["task_id"]},
            )
            e.step()
        else:
            build = e.to_stage(build, "embed")
            e.plan(e.next_scope(build["task_id"]), "embedding", [{"fault": "bad_vector"}])
            e.finish("/api/v3/index-builds/" + build["index_batch_id"], successful=False)
        current = e.request("GET", "/api/v3/documents/" + doc["document_id"])
        c.equal(
            current["active_index_batch_id"], doc["active_index_batch_id"], "旧active保留：" + mode
        )
        c.equal(
            current["latest_build"]["index_batch_id"], build["index_batch_id"], "latest仍为本次尝试"
        )
        c.check(current["latest_build"]["state"] in {"failed", "cancelled"}, "新尝试明确终态")


def idx006(c):
    # IDX_006：真实队列失租换代，迟到旧代没有发布权限。
    from backend.workers.handlers.index_build_handler import process_index_build_task

    e = c.environment()
    doc = e.upload(finish=False)
    build = e.to_stage(doc, "publish")
    e.sql(
        "UPDATE tasks SET available_at=now()-interval '1 second' WHERE task_id=:id",
        {"id": build["task_id"]},
    )

    async def claim():
        async with e.app.state.session_factory() as session:
            # 前一阶段已释放为waiting_external；按正式回收流程转queued后再领取。
            await e.runtime.queue(session).reclaim()
            task = await e.runtime.queue(session).claim("old-worker")
            if task is None:
                raise ValueError("IDX_006_EXPECTED_CLAIMABLE_TASK")
            await e.runtime.queue(session).start(task)
            return task

    task = e.call(claim)
    e.sql(
        "UPDATE tasks SET lease_expires_at=now()-interval '1 second' WHERE task_id=:id",
        {"id": task.task_id},
    )
    e.step()
    c.rejects(
        lambda: e.call(
            process_index_build_task,
            e.app.state.session_factory,
            e.settings,
            task.task_id,
            task.worker_id,
            task.generation,
        )
    )
    c.equal(
        e.request("GET", "/api/v3/index-builds/" + build["index_batch_id"])["state"],
        "succeeded",
        "旧代不能覆盖新代成功",
    )


def idx007(c):
    # IDX_007：在flush之后推进受控时间，检验最后一次授权检查回滚。
    from unittest.mock import patch

    from backend.db.models import utc_now
    from backend.workers.handlers import index_build_handler as handler

    e = c.environment()
    doc = e.upload(finish=False)
    e.to_stage(doc, "publish")
    original = handler.check_locked_times

    def expired(lease, deadline):
        from backend.application.task_execution import ExecutionStopped

        if lease <= utc_now() + timedelta(seconds=100):
            raise ExecutionStopped()
        return original(lease, deadline)

    with patch.object(handler, "check_locked_times", expired):
        e.step()
    c.equal(
        e.request("GET", "/api/v3/documents/" + doc["document_id"])["active_index_batch_id"],
        None,
        "最终授权失败不切active",
    )
    c.check(e.sql("SELECT state FROM index_builds")[0]["state"] != "succeeded", "成功事实回滚")


def idx008(c):
    # IDX_008：每阶段换Worker身份，检查点续跑不重造Document/Chunk。
    from backend.workers.runtime import WorkerRuntime

    e = c.environment()
    doc = e.upload(finish=False)
    for _ in range(12):
        worker = WorkerRuntime(e.settings, e.app.state.session_factory, e.app.state.notifier)
        e.step(runtime=worker)
        row = e.request("GET", "/api/v3/index-builds/" + doc["latest_build"]["index_batch_id"])
        if row["state"] == "succeeded":
            break
    c.equal(row["state"], "succeeded", "跨Worker续同一Build成功")
    c.equal(e.sql("SELECT count(*) n FROM documents")[0]["n"], 1, "不造新Document")
    c.equal(e.sql("SELECT count(*) n FROM chunks")[0]["n"], row["chunk_count"], "检查点不重复写片")


def idx009(c):
    # IDX_009：active/latest跨文档关系由实际FK拒绝。
    e = c.environment()
    a, b = e.upload(), e.upload()
    for field in ("active_index_batch_id", "latest_index_batch_id"):
        c.rejects(
            lambda field=field: e.sql(
                f"UPDATE documents SET {field}=:batch WHERE document_id=:id",
                {"batch": b["active_index_batch_id"], "id": a["document_id"]},
            )
        )


def idx010(c):
    # IDX_010：两个PG请求竞争冻结视图与标签修订，只能整集。
    e = c.environment()
    doc = e.upload(tags=["old"])
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(
            e.client.post,
            "/api/v3/retrieval-executions",
            json={"query": "ALPHA", "knowledge_base_id": e.base, "filters": {"tags_all": ["old"]}},
            headers={"Idempotency-Key": str(uuid4())},
        )
        second = pool.submit(
            e.client.patch, "/api/v3/documents/" + doc["document_id"], json={"tags": ["new"]}
        )
        a, b = first.result(), second.result()
    c.equal((a.status_code, b.status_code), (202, 200), "竞争双方均可完成")
    execution = e.finish("/api/v3/retrieval-executions/" + a.json()["execution_id"])
    items = e.sql(
        "SELECT index_batch_id FROM retrieval_view_items WHERE view_id=:id",
        {"id": execution["view_id"]},
    )
    c.check(
        items == [] or [r["index_batch_id"] for r in items] == [doc["active_index_batch_id"]],
        "视图为竞争前/后完整集合",
    )


def idx011(c):
    # IDX_011：成功Build/Artifact配置文本不可改。
    e = c.environment()
    e.upload()
    for query in (
        "UPDATE index_builds SET manifest_hash='bad'",
        "UPDATE index_builds SET chunker_snapshot='{}'",
        "UPDATE parsed_artifacts SET text='forged'",
        "UPDATE parsed_artifacts SET text_hash='bad'",
    ):
        c.rejects(lambda query=query: e.sql(query))


CASES = {
    **{f"VEC_{n:03}": globals()[f"vec{n:03}"] for n in range(1, 9)},
    **{f"IDX_{n:03}": globals()[f"idx{n:03}"] for n in range(1, 12)},
}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
