"""RET/ENH与可控EVAL：真实PG召回、范围、重排及证据，不用同一冒烟充数。"""

import asyncio
import copy
import hashlib
import json
import math
from unittest.mock import patch
from uuid import uuid4

import httpx
from helpers.case_runner import run_category
from helpers.common import SUITE, load
from helpers.evidence_capture import evidence_prefix, validate_capture
from sqlalchemy import event, select

from backend.application.evidence_assembly import assemble_evidence
from backend.application.retrieval_views import load_scope
from backend.db.models import ChunkModel
from backend.domain.rag import RetrievalPolicy
from backend.domain.rag_profiles import RerankConfig
from backend.infrastructure.providers.bailian_rerank import BailianRerank
from backend.infrastructure.rag.vector_search import VectorSearch


def scope(e, view):
    async def get():
        async with e.app.state.session_factory() as session:
            return await load_scope(session, e.settings, view)

    return e.call(get)


def search(e, view, vector=None, count=20):
    async def query():
        async with e.app.state.session_factory() as session:
            frozen = await load_scope(session, e.settings, view)
            rows = (
                await session.scalars(
                    select(ChunkModel).where(ChunkModel.index_batch_id.in_(frozen.batches))
                )
            ).all()
            value = vector if vector is not None else list(rows[0].embedding)
            return await VectorSearch(session).search(frozen, value, count), rows

    return e.call(query)


def assemble(e, hits, **kwargs):
    async def execute():
        async with e.app.state.session_factory() as session:
            return await assemble_evidence(session, hits, RetrievalPolicy(**kwargs))

    return e.call(execute)


def rerank_protocol(c, *, query="query", texts=("one", "two"), body=None, status=200, **changes):
    config = copy.deepcopy(
        next(
            r["config"]
            for r in load(SUITE / "fixtures/profiles.real.example.json")
            if r["profile_id"] == "bailian-rerank"
        )
    )
    config.update(changes)
    calls = []

    def response(request):
        calls.append(json.loads(request.content))
        return httpx.Response(
            status,
            json=body
            or {
                "output": {
                    "results": [
                        {"index": i, "relevance_score": 0.9 - i * 0.1} for i in range(len(texts))
                    ]
                }
            },
        )

    provider = BailianRerank(
        RerankConfig.model_validate(config),
        "dummy-protocol-only",
        transport=httpx.MockTransport(response),
    )
    result = asyncio.run(provider.rank(query, texts))
    c.note("执行", {"证据层": "原生rerank协议模拟", "调用数": len(calls)})
    return result, provider, calls


def ret001(c):
    # RET_001：诊断原query hash不改写，Run原锚点与历史干扰独立。
    e = c.environment()
    e.upload()
    query = "  原文 ALPHA🙂  "
    result = e.diagnostic(query=query)
    c.equal(
        e.sql(
            "SELECT query_hash FROM retrieval_executions WHERE execution_id=:id",
            {"id": result["execution_id"]},
        )[0]["query_hash"],
        hashlib.sha256(query.encode()).hexdigest(),
        "query原文hash",
    )
    e.request(
        "POST",
        "/api/v3/retrieval-executions",
        expected=(422,),
        json={"query": "中" * 3000, "knowledge_base_id": e.base},
        headers={"Idempotency-Key": str(uuid4())},
    )
    # DTO允许非零长度空白串，正式Worker在向量外发前拒绝；验收目标不要求同步422。
    result = e.diagnostic(query=" ", finish=False)
    row = e.finish("/api/v3/retrieval-executions/" + result["execution_id"], successful=False)
    c.equal(row["error_code"], "RETRIEVAL_QUERY_TOO_LONG", "空白query明确失败而非empty成功")


def ret002(c):
    # RET_002：document/extensions OR、维度AND、tags_all全满足，显式空不同于缺省。
    e = c.environment()
    docs = [
        e.upload(filename="a.txt", tags=["a", "b"]),
        e.upload(filename="b.md", tags=["a"]),
        e.upload(filename="c.txt", tags=["b"]),
    ]
    groups = [
        ({}, 3),
        ({"document_ids": []}, 0),
        ({"extensions": []}, 0),
        ({"tags_all": []}, 3),
        ({"extensions": [".txt"]}, 2),
        ({"tags_all": ["a", "b"]}, 1),
        (
            {
                "document_ids": [docs[0]["document_id"], docs[1]["document_id"]],
                "extensions": [".md"],
            },
            1,
        ),
    ]
    for filters, expected in groups:
        row = e.diagnostic(filters=filters)
        c.equal(
            len(
                e.sql(
                    "SELECT * FROM retrieval_view_items WHERE view_id=:id", {"id": row["view_id"]}
                )
            ),
            expected,
            "过滤范围组合：" + str(filters),
        )


def ret003(c):
    # RET_003：混入一个越权/异库/不存在ID应全拒绝。
    e = c.environment()
    doc = e.upload()
    other = e.request(
        "POST",
        "/api/v3/knowledge-bases",
        expected=(201,),
        json={
            "name": "other",
            "embedding_profile_id": "mock-embedding",
            "embedding_profile_version": 1,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    foreign = e.upload(base=other["knowledge_base_id"])
    for identity in (foreign["document_id"], str(uuid4())):
        e.request(
            "POST",
            "/api/v3/retrieval-executions",
            expected=(404,),
            json={
                "query": "x",
                "knowledge_base_id": e.base,
                "filters": {"document_ids": [doc["document_id"], identity]},
            },
            headers={"Idempotency-Key": str(uuid4())},
        )


def ret004(c):
    # RET_004：冻结后新增/重建/改标签不展开旧view。
    e = c.environment()
    doc = e.upload(tags=["old"])
    first = e.diagnostic()
    original = scope(e, first["view_id"])
    e.upload(raw=b"new doc")
    e.request("PATCH", "/api/v3/documents/" + doc["document_id"], json={"tags": ["changed"]})
    build = e.request(
        "POST",
        "/api/v3/documents/" + doc["document_id"] + "/index-builds",
        expected=(202,),
        json={},
        headers={"Idempotency-Key": str(uuid4())},
    )
    e.finish("/api/v3/index-builds/" + build["index_batch_id"])
    c.equal(scope(e, first["view_id"]), original, "旧view身份/集合不变")
    c.check(
        build["index_batch_id"] in scope(e, e.diagnostic()["view_id"]).batches, "新view取当前active"
    )


def ret005(c):
    # RET_005：坏view hash不得兜底最新。若PG不可变守卫先拒绝，同样证明不能带坏事实查询。
    e = c.environment()
    e.upload()
    row = e.diagnostic()
    try:
        e.sql(
            "UPDATE retrieval_views SET manifest_hash='bad' WHERE view_id=:id",
            {"id": row["view_id"]},
        )
    except Exception:
        c.check(True, "PG拒绝破坏冻结view")
    else:
        c.rejects(lambda: scope(e, row["view_id"]), codes={"RETRIEVAL_VIEW_UNAVAILABLE"})


def ret006(c):
    # RET_006：空视图合法empty，无Embedding/rerank调用。
    e = c.environment()
    row = e.diagnostic(overrides={"rerank_enabled": True})
    c.equal((row["mode"], row["candidates"], row["bundle_ids"]), ("empty", [], []), "合法空检索")
    task = e.sql(
        "SELECT task_id,generation FROM tasks WHERE retrieval_execution_id=:id",
        {"id": row["execution_id"]},
    )[0]
    calls = e.observations(task["task_id"] + ":" + str(task["generation"]))
    c.equal((calls["embedding"]["count"], calls["rerank"]["count"]), (0, 0), "空视图零付费能力调用")


def ret007(c):
    # RET_007：独立数学cosine oracle，实际PG SQL必须ORDER/LIMIT/距离。
    e = c.environment()
    for i in range(3):
        e.upload(raw=(f"ALPHA {i}\n" * 200).encode())
    row = e.diagnostic()
    statements = []

    def capture(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    event.listen(e.app.state.engine.sync_engine, "before_cursor_execute", capture)
    try:
        hits, rows = search(e, row["view_id"])
    finally:
        event.remove(e.app.state.engine.sync_engine, "before_cursor_execute", capture)
    vector = [float(v) for v in rows[0].embedding]

    def cosine(row):
        values = list(row.embedding)
        return sum(a * b for a, b in zip(vector, values, strict=False)) / (
            math.sqrt(sum(a * a for a in vector)) * math.sqrt(sum(b * b for b in values))
        )

    expected = sorted(
        rows, key=lambda r: (-cosine(r), r.document_id, r.index_batch_id, r.seq, r.chunk_id)
    )[:20]
    c.equal([r.chunk_id for r in hits], [r.chunk_id for r in expected], "PG身份/排序匹配独立oracle")
    c.check(
        all(
            abs(hit.dense_score - cosine(ref)) <= 1e-5
            for hit, ref in zip(hits, expected, strict=False)
        ),
        "cosine分数误差≤1e-5",
    )
    c.check(
        any("<=>" in s and "ORDER BY" in s and "LIMIT" in s for s in statements),
        "实际数据库Top-K SQL",
    )


def ret008(c):
    # RET_008：混维范围先物化，候选和外view不能参与距离。
    e = c.environment()
    doc = e.upload()
    e.import_profiles(
        [
            {
                "kind": "embedding",
                "profile_id": "other-1024",
                "version": 1,
                "config": {"space": {"model": "other", "revision": "r1", "dimension": 1024}},
            }
        ]
    )
    other = e.request(
        "POST",
        "/api/v3/knowledge-bases",
        expected=(201,),
        json={"name": "1024", "embedding_profile_id": "other-1024", "embedding_profile_version": 1},
        headers={"Idempotency-Key": str(uuid4())},
    )
    e.upload(base=other["knowledge_base_id"])
    view = e.diagnostic()["view_id"]
    hits, _ = search(e, view)
    c.equal({h.document_id for h in hits}, {doc["document_id"]}, "混维及外库不混查")
    statements = []

    def capture(_conn, _cursor, statement, *_):
        statements.append(statement)

    event.listen(e.app.state.engine.sync_engine, "before_cursor_execute", capture)
    try:
        search(e, view)
    finally:
        event.remove(e.app.state.engine.sync_engine, "before_cursor_execute", capture)
    c.check(any("MATERIALIZED" in s and "<=>" in s for s in statements), "授权范围先物化再求距")


def ret009(c):
    # RET_009：相同文本向量并列，跨文档稳定键顺序。
    e = c.environment()
    for _ in range(3):
        e.upload(raw=b"identical")
    view = e.diagnostic()["view_id"]
    a, _ = search(e, view, count=2)
    b, _ = search(e, view, count=2)
    c.equal([h.chunk_id for h in a], [h.chunk_id for h in b], "有限K并列稳定")
    c.equal(
        [(h.document_id, h.index_batch_id, h.seq, h.chunk_id) for h in a],
        sorted((h.document_id, h.index_batch_id, h.seq, h.chunk_id) for h in a),
        "稳定键排序",
    )


def ret010(c):
    # RET_010：candidate/top_k联动与不足不补他库。
    c.equal((RetrievalPolicy().candidate_k, RetrievalPolicy().top_k), (20, 5), "默认20/5")
    for values in (
        {"top_k": 0},
        {"top_k": 21},
        {"candidate_k": 101},
        {"candidate_k": 4, "top_k": 5},
    ):
        c.rejects(lambda values=values: RetrievalPolicy(**values), error_types=(ValueError,))
    e = c.environment()
    e.upload()
    row = e.diagnostic(overrides={"top_k": 20})
    c.equal(len(row["candidates"]), 1, "候选不足只取实际数")


def ret011(c):
    # RET_011：关闭重排无调用，保留dense排序。
    e = c.environment()
    e.upload()
    row = e.diagnostic(overrides={"rerank_enabled": False})
    task = e.sql(
        "SELECT task_id,generation FROM tasks WHERE retrieval_execution_id=:id",
        {"id": row["execution_id"]},
    )[0]
    c.equal(
        e.observations(task["task_id"] + ":" + str(task["generation"]))["rerank"]["count"],
        0,
        "关闭零调用",
    )
    c.check(all(v["rerank_score"] is None for v in row["candidates"]), "不伪造重排分数")


def ret012(c):
    # RET_012：只用原候选index重排，非法身份全拒绝。
    good = {
        "output": {
            "results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]
        }
    }
    c.equal(rerank_protocol(c, body=good)[0], ((1, 0.9), (0, 0.2)), "原候选交换身份")
    for rows in (
        [{"index": 0, "relevance_score": 0.5}],
        [{"index": 0, "relevance_score": 0.5}] * 2,
        [{"index": 0.0, "relevance_score": 0.5}, {"index": 1, "relevance_score": 0.2}],
        [{"index": 0, "relevance_score": 0.5}, {"index": 2, "relevance_score": 0.2}],
    ):
        c.rejects(
            lambda rows=rows: rerank_protocol(c, body={"output": {"results": rows}}),
            codes={"RERANK_PROTOCOL_INVALID"},
        )


def ret013(c):
    # RET_013：重排非法数值拒绝，dense/重排分数分别保存。
    for value in (math.nan, math.inf, -0.1, 1.1, "0.5"):
        c.rejects(
            lambda value=value: rerank_protocol(
                c,
                body={
                    "output": {
                        "results": [
                            {"index": 0, "relevance_score": value},
                            {"index": 1, "relevance_score": 0.2},
                        ]
                    }
                },
            )
        )
    e = c.environment()
    e.upload()
    row = e.diagnostic(overrides={"rerank_enabled": True})
    c.check(
        all("dense_score" in r and r["rerank_score"] is not None for r in row["candidates"]),
        "两类分数并存",
    )


def ret014(c):
    # RET_014：UTF-8前缀范围与组合预算，query不能静默截断。
    c.rejects(lambda: rerank_protocol(c, query="x" * 2049), codes={"RERANK_INPUT_BUDGET_EXCEEDED"})
    _, provider, calls = rerank_protocol(
        c, texts=("🙂中" * 1000, "second"), max_document_bytes=20, max_request_bytes=128
    )
    documents = calls[0]["input"]["documents"]
    c.check(all(len(s.encode()) <= 20 for s in documents), "每个文档按字节前缀截取")
    c.equal(
        provider.input_ranges, tuple((0, len(s)) for s in documents), "trace字符范围对应实际请求"
    )


def fail_policy(c, fallback, status, expected):
    e = c.environment()
    e.upload()
    e.import_profiles(
        [
            {
                "kind": "retrieval",
                "profile_id": "failure-policy",
                "version": 1,
                "config": {
                    "policy": {"rerank_enabled": True, "failure_policy": fallback},
                    "rerank_profile_id": "mock-rerank",
                    "rerank_profile_version": 1,
                },
            }
        ]
    )
    row = e.diagnostic(finish=False, retrieval_profile_id="failure-policy")
    task = e.sql(
        "SELECT task_id FROM tasks WHERE retrieval_execution_id=:id", {"id": row["execution_id"]}
    )[0]
    for generation in range(1, 4):
        e.plan(task["task_id"] + ":" + str(generation), "rerank", [{"status": status}])
    result = e.finish("/api/v3/retrieval-executions/" + row["execution_id"], successful=False)
    c.equal(
        result["mode"] if result["state"] == "succeeded" else result["state"],
        expected,
        "失败策略明确且不伪空",
    )
    return e, result


def ret015(c):
    # RET_015：默认fail不继续生成成功。
    fail_policy(c, "fail", 503, "failed")


def ret016(c):
    # RET_016：只有显式dense_fallback可降级，原dense身份保留。
    e, row = fail_policy(c, "dense_fallback", 503, "degraded")
    c.equal(row["error_code"], "RERANK_TEMPORARY_UNAVAILABLE", "降级保留原因")
    c.check(
        row["candidates"] and all(r["rerank_score"] is None for r in row["candidates"]),
        "降级不造分数",
    )


def ret017(c):
    # RET_017：认证错误即使fallback也失败。
    _, row = fail_policy(c, "dense_fallback", 401, "failed")
    c.equal(row["error_code"], "RERANK_AUTH_FAILED", "认证不在降级名单")


def ret019(c):
    # RET_019：诊断Task/View不产生聊天事实。
    e = c.environment()
    e.upload()
    row = e.diagnostic()
    c.equal(row["origin"], "diagnostic", "独立来源")
    for table in ("threads", "messages", "runs"):
        c.equal(e.sql(f"SELECT count(*) n FROM {table}")[0]["n"], 0, "诊断不创建" + table)


def ret020(c):
    # RET_020：诊断取消和越owner边界。
    e = c.environment()
    row = e.diagnostic(finish=False)
    result = e.request(
        "POST",
        "/api/v3/retrieval-executions/" + row["execution_id"] + "/cancel",
        expected=(200, 202),
    )
    c.equal(result["state"], "cancelled", "排队诊断可取消")
    e.settings.owner_id = "rag-test-owner-b"
    e.request(
        "POST", "/api/v3/retrieval-executions/" + row["execution_id"] + "/cancel", expected=(404,)
    )


def ret021(c):
    # RET_021：off/empty与有证据ok事实分开。
    e = c.environment()
    off = e.run(enabled=False)
    events = e.request("GET", "/api/v3/runs/" + off["run_id"] + "/events")["events"]
    c.check(
        any(r["type"] == "retrieval.completed" and r["data"]["mode"] == "off" for r in events),
        "关闭明确off",
    )
    c.equal(e.diagnostic()["mode"], "empty", "空库empty")
    e.upload()
    c.equal(e.diagnostic()["mode"], "ok", "有证据ok")


def ret022(c):
    # RET_022：真实Run->ToolCall->Execution->View->Context/Citation身份链。
    e = c.environment()
    e.upload()
    run = e.run()
    rows = e.sql(
        (
            "SELECT t.run_id,t.generation,t.execution_id,r.view_id FROM tool_c"
            "alls t JOIN retrieval_executions r ON r.execution_id=t.execution_"
            "id WHERE t.run_id=:id"
        ),
        {"id": run["run_id"]},
    )
    c.equal(len(rows), 1, "每代一个工具执行链")
    c.check(
        e.sql("SELECT * FROM retrieval_view_items WHERE view_id=:id", {"id": rows[0]["view_id"]}),
        "可追到冻结批次",
    )
    c.check(e.sql("SELECT * FROM context_evidence_ranges"), "实际Context范围存在")


def ret023(c):
    # RET_023：合法发布行批量夹具验证范围1000/1001，不用切前1000掩盖。
    e = c.environment()
    from helpers.synthetic_rows import seed_published_documents

    seed_published_documents(e, 1000)
    c.equal(
        len(scope(e, e.diagnostic(finish=False)["view_id"]).batches),
        1000,
        "1000批次可冻结；范围夹具不冒充解析/增强成功",
    )
    seed_published_documents(e, 1, start=1000)
    e.request(
        "POST",
        "/api/v3/retrieval-executions",
        expected=(422,),
        json={"query": "ALPHA", "knowledge_base_id": e.base},
        headers={"Idempotency-Key": str(uuid4())},
    )


def enhance_fixture(c):
    e = c.environment()
    e.upload(raw=("ALPHA第一条件37。\n" * 80 + "BETA第二条件蓝色。\n" * 80).encode())
    view = e.diagnostic()["view_id"]
    hits, _ = search(e, view)
    return e, sorted(hits, key=lambda h: h.seq)


def enh001(c):
    # ENH_001：首中尾和0/1/2半径不跨文档/批次。
    e, hits = enhance_fixture(c)
    for anchor in (hits[0], hits[len(hits) // 2], hits[-1]):
        for radius in (0, 1, 2):
            bundles, _ = assemble(e, [anchor], neighbor_radius=radius)
            expected = [h for h in hits if abs(h.seq - anchor.seq) <= radius]
            c.equal(
                {v["chunk_id"] for v in bundles[0]["components"]},
                {h.chunk_id for h in expected},
                "邻近范围准确",
            )


def enh002(c):
    # ENH_002：多个重叠锚点只合并同文档规范文本并集。
    e, hits = enhance_fixture(c)
    bundles, _ = assemble(e, hits[:2], neighbor_radius=1)
    c.equal(len(bundles), 1, "重叠范围合并")
    text = e.sql("SELECT text FROM parsed_artifacts")[0]["text"]
    b = bundles[0]
    c.equal(b["text"], text[b["start_offset"] : b["end_offset"]], "正文无重复拼接")


def enh003(c):
    # ENH_003：字符预算前/等于/超过和去除原因。
    e, hits = enhance_fixture(c)
    for budget in (1, 40, 800):
        bundles, omitted = assemble(e, hits[:3], max_enhanced_chars=budget)
        c.check(sum(len(r["text"]) for r in bundles) <= budget, "总字符预算有界")
        c.check(sum(len(r["components"]) for r in bundles) <= 100, "组成上限100")
        c.check(
            omitted
            and all(
                r["reason"] in {"enhancement_truncated", "enhancement_budget"} for r in omitted
            ),
            "删减有原因",
        )


def enh004(c):
    # ENH_004：Bundle各组件身份/range/hash自洽。
    e, hits = enhance_fixture(c)
    bundles, _ = assemble(e, hits[:2])
    artifact = e.sql("SELECT text FROM parsed_artifacts")[0]["text"]
    rows = {r["chunk_id"]: r for r in e.sql("SELECT * FROM chunks")}
    for bundle in bundles:
        for component in bundle["components"]:
            row = rows[component["chunk_id"]]
            c.equal(
                (row["document_id"], row["index_batch_id"]),
                (bundle["document_id"], bundle["index_batch_id"]),
                "组成身份一致",
            )
            c.equal(
                component["content_hash"],
                hashlib.sha256(
                    artifact[component["start_offset"] : component["end_offset"]].encode()
                ).hexdigest(),
                "实际区间hash",
            )


def enh005(c):
    # ENH_005：增强裁半行/Unicode时来源同步裁剪。
    e, hits = enhance_fixture(c)
    bundle = assemble(e, hits[:1], max_enhanced_chars=17)[0][0]
    c.equal(len(bundle["text"]), 17, "预算字符裁剪")
    c.check(
        all(
            bundle["start_offset"] <= p["start_offset"] < p["end_offset"] <= bundle["end_offset"]
            for p in bundle["locations"]
        ),
        "来源范围不超过实际正文",
    )


def enh006(c):
    # ENH_006：知道Bundle ID不授予跨owner访问。
    e, _ = enhance_fixture(c)
    row = e.diagnostic()
    identity = row["bundle_ids"][0]
    e.settings.owner_id = "rag-test-owner-b"
    e.request("GET", "/api/v3/evidence-bundles/" + identity, expected=(404,))
    e.request("GET", "/api/v3/evidence-bundles/" + str(uuid4()), expected=(404,))


def enh007(c):
    # ENH_007：组件hash坏数据只能拒绝，不替换当前active。
    e, _ = enhance_fixture(c)
    result = e.diagnostic()
    identity = result["bundle_ids"][0]
    try:
        e.sql(
            "UPDATE evidence_components SET content_hash='bad' WHERE bundle_id=:id",
            {"id": identity},
        )
    except Exception:
        c.check(True, "PG不可变约束直接拒绝破坏")
    else:
        e.request("GET", "/api/v3/evidence-bundles/" + identity, expected=(409,))


def enh008(c):
    # ENH_008：正文分页不平移Artifact组件坐标。
    e = c.environment()
    e.upload(raw=("分页🙂\n" * 1800).encode())
    row = e.diagnostic()
    identity = row["bundle_ids"][0]
    _full, offset, parts, components = "", 0, [], None
    while True:
        page = e.request("GET", "/api/v3/evidence-bundles/" + identity, params={"offset": offset})
        c.check(len(page["text"]) <= 4000, "单页不超4000")
        if components is not None:
            c.equal(page["components"], components, "翻页不平移组件坐标")
        components = page["components"]
        parts.append(page["text"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    c.check("".join(parts), "续读得到正文")
    for offset in (-1, 64001):
        e.request(
            "GET",
            "/api/v3/evidence-bundles/" + identity,
            expected=(422,),
            params={"offset": offset},
        )


def enh009(c):
    # ENH_009：新active重建后旧Bundle仍逐字段一致。
    e = c.environment()
    doc = e.upload()
    row = e.diagnostic()
    path = "/api/v3/evidence-bundles/" + row["bundle_ids"][0]
    before = e.request("GET", path)
    build = e.request(
        "POST",
        "/api/v3/documents/" + doc["document_id"] + "/index-builds",
        expected=(202,),
        json={"chunker": {"size": 200, "overlap": 20}},
        headers={"Idempotency-Key": str(uuid4())},
    )
    e.finish("/api/v3/index-builds/" + build["index_batch_id"])
    c.equal(e.request("GET", path), before, "历史正文/hash/位置不漂移")


def budget_run(c, e, *, radius, expect_evidence, chars=16000, window=8192):
    # EVAL_004/005：固定真实PG候选身份，其余完整Run、预算、发布和引用均走产品。
    from backend.application import session_execution
    from backend.infrastructure.session.model_profiles import SQLModelProfileRepository

    identity = "eval-" + uuid4().hex[:12]
    profile = copy.deepcopy(load(SUITE / "fixtures/models.local.json")[0])
    profile.update(
        profile_id=identity, is_default=False, context_window_tokens=window, max_output_tokens=128
    )
    profile["tokenizer_config"]["safety_margin_tokens"] = 64

    async def import_model():
        async with e.app.state.session_factory() as session:
            await SQLModelProfileRepository(session).import_profiles(
                [*load(SUITE / "fixtures/models.local.json"), profile]
            )
            await session.commit()

    e.call(import_model)
    e.import_profiles(
        [
            {
                "kind": "retrieval",
                "profile_id": identity,
                "version": 1,
                "config": {
                    "policy": {
                        "candidate_k": 20,
                        "top_k": 1,
                        "neighbor_radius": radius,
                        "max_enhanced_chars": chars,
                    }
                },
            }
        ]
    )
    inputs = []

    class Capture:
        async def stream_request(self, request):
            inputs.extend(m.content for m in request.messages if evidence_prefix(m.content))
            yield "确定性合成回答；来源只以实际Context关联为准。"

    original = VectorSearch.search

    async def fixed_first(self, frozen, vector, count):
        hits = await original(self, frozen, vector, 100)
        return tuple(sorted(hits, key=lambda h: h.seq)[:1])

    with (
        patch.object(VectorSearch, "search", fixed_first),
        patch.object(session_execution, "provider_from_snapshot2", lambda _: Capture()),
    ):
        run = e.run(
            content="ALPHA的两个条件是什么？",
            model_profile_id=identity,
            model_profile_version=1,
            rag={
                "enabled": True,
                "knowledge_base_id": e.base,
                "retrieval_profile_id": identity,
                "retrieval_profile_version": 1,
            },
        )
    plan = e.sql("SELECT * FROM context_plans WHERE run_id=:id", {"id": run["run_id"]})[0]
    ranges = e.sql(
        "SELECT * FROM context_evidence_ranges WHERE plan_id=:id", {"id": plan["context_plan_id"]}
    )
    selected_ids = {v for item in plan["selected_evidence"] for v in item["context_evidence_ids"]}
    citations = e.sql(
        "SELECT citations_json FROM messages WHERE role='assistant' AND run_id=:id",
        {"id": run["run_id"]},
    )[0]["citations_json"]
    c.equal({r["context_evidence_id"] for r in ranges}, selected_ids, "Context实际范围与计划一致")
    c.equal(
        {v for item in citations for v in item["context_evidence_ids"]},
        selected_ids,
        "最终引用不包含被预算丢弃的范围",
    )
    execution = e.sql(
        "SELECT candidates_json,omitted_json FROM retrieval_executions WHERE run_id=:id",
        {"id": run["run_id"]},
    )[0]
    c.check(execution["candidates_json"], "四组均实际召回同一已发布来源")
    numbers = validate_capture(inputs, expect_evidence=expect_evidence)
    c.check(not expect_evidence or bool(inputs), "预期有证据时实际捕获非空")
    c.check(len(numbers) == len(inputs), "所有实际捕获证据均严格校验来源编号")
    text = "\n".join(inputs)
    c.note(
        "观察",
        {
            "run_id": run["run_id"],
            "半径": radius,
            "增强预算": chars,
            "生成窗口": window,
            "实际证据输入hash": hashlib.sha256(text.encode()).hexdigest(),
            "输入字符": len(text),
            "选入范围数": len(ranges),
            "增强删除": execution["omitted_json"],
            "生成删除": plan["omitted_evidence"],
        },
    )
    return text, plan, ranges


def eval004(c):
    # EVAL_004：两个必要事实跨片，比较两次完整Run实际模型输入，非诊断Bundle长度。
    e = c.environment()
    source = "ALPHA的第一条件是37。" + "填充。" * 260 + "ALPHA的第二条件是蓝色。"
    e.upload(raw=source.encode())
    without, _, _ = budget_run(c, e, radius=0, expect_evidence=True)
    enhanced, _, _ = budget_run(c, e, radius=2, expect_evidence=True)
    c.check(
        "第一条件是37" in without and "第二条件是蓝色" not in without,
        "半径0实际Context缺失第二条件",
    )
    c.check(
        "第一条件是37" in enhanced and "第二条件是蓝色" in enhanced,
        "增强实际进入Context并补齐两个必要条件",
    )


def eval005(c):
    # EVAL_005：增强预算×模型窗口四个实际Run；判定最终输入、删减原因及引用。
    e = c.environment()
    e.upload(raw=("ALPHA的第一条件是37。" + "填充。" * 260 + "ALPHA的第二条件是蓝色。").encode())
    outcomes = {}
    for chars in (16000, 20):
        for window in (8192, 512):
            text, plan, ranges = budget_run(
                c,
                e,
                radius=2,
                chars=chars,
                window=window,
                expect_evidence=not (chars == 16000 and window == 512),
            )
            outcomes[chars, window] = text
            if chars == 20:
                c.check(all(r["end_offset"] <= 20 for r in ranges), "增强裁剪后引用不得越过20字符")
            if chars == 16000 and window == 512:
                c.check(
                    not text and not ranges and plan["omitted_evidence"],
                    "生成窗口不足移除整Bundle并记录原因",
                )
    c.check("第二条件是蓝色" in outcomes[16000, 8192], "双预算足够时答案范围进入模型")
    c.check(
        all(
            "第二条件是蓝色" not in value for key, value in outcomes.items() if key != (16000, 8192)
        ),
        "任一预算移除后不得冒称最终范围仍支持第二条件",
    )


CASES = {
    **{f"RET_{n:03}": globals()[f"ret{n:03}"] for n in list(range(1, 18)) + list(range(19, 24))},
    **{f"ENH_{n:03}": globals()[f"enh{n:03}"] for n in range(1, 10)},
    "EVAL_004": eval004,
    "EVAL_005": eval005,
}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
