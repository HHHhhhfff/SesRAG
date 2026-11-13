"""EVAL_007/008：生产PG召回计量与阶段分解；Mock延迟不作真实服务SLO。"""

import asyncio
import json
import math
import os
import statistics
import time
from contextlib import ExitStack
from unittest.mock import patch

from helpers.case_runner import run_category
from sqlalchemy import event, select, text

from backend.application.retrieval_views import load_scope
from backend.db.models import ChunkModel
from backend.infrastructure.rag.vector_search import VectorSearch


def eval001(c):
    # 原源投影独立于产品解析与检索；不把金标存在当真实效果通过。
    from helpers.common import SUITE, load
    from helpers.source_annotations import audit_annotations

    value = load(SUITE / "fixtures/source-annotations.json")
    result = audit_annotations(value)
    c.equal(result["questions"], 25, "独立问句及答案/无答案依据共25题")
    c.equal(result["answerable"], 20, "有答案20题与无答案5题")
    c.equal(len(result["formats"]), 9, "九格式原源hash及投影区间逐一核验")
    c.note("观察", result)
    c.check(
        all("artifact_sha256" not in r for q in value["questions"] for r in q["ranges"]),
        "原源标注没有伪造云产物hash",
    )


def eval007(c):
    # EVAL_007：正式解析/切片/向量化/发布生成10000有效片段，原始计时完整归档。
    e = c.environment()
    doc = e.upload(raw=b"X" * 640000, finish=False)
    batch = doc["latest_build"]["index_batch_id"]
    # 明示性能前置注入：仅修改尚未开始的候选配置；不用成功事实或不可变触发器旁路。
    e.sql(
        "UPDATE index_builds SET chunker_snapshot=:config WHERE index_batch_id=:id",
        {"config": json.dumps({"mode": "character_v1", "size": 64, "overlap": 0}), "id": batch},
    )
    e.finish("/api/v3/index-builds/" + batch, steps=1000)
    count = e.sql(
        "SELECT count(*) n FROM chunks WHERE index_batch_id=:id AND embedding IS NOT NULL",
        {"id": batch},
    )[0]["n"]
    c.check(count >= 10000, "性能数据至少10000有效Chunk", count)
    execution = e.diagnostic()

    async def measure():
        samples, statements = [], []
        engine = e.app.state.engine

        def capture(_conn, _cursor, sql, _params, _ctx, _many):
            if "scoped" in sql and len(statements) < 1:
                statements.append(sql)

        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            async with e.app.state.session_factory() as session:
                scope = await load_scope(session, e.settings, execution["view_id"])
                vector = list(
                    (
                        await session.scalar(
                            select(ChunkModel).where(ChunkModel.index_batch_id == batch)
                        )
                    ).embedding
                )
                search = VectorSearch(session)
                for _ in range(100):
                    await search.search(scope, vector, 20)
                failures = 0
                for _ in range(100):
                    started = time.perf_counter()
                    try:
                        hits = await search.search(scope, vector, 20)
                        if len(hits) != 20:
                            failures += 1
                    except Exception:
                        failures += 1
                    samples.append((time.perf_counter() - started) * 1000)
                metadata = dict(
                    (
                        await session.execute(
                            text(
                                "SELECT version() pg, (SELECT extversion "
                                "FROM pg_extension WHERE extname='vector') vector"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)
        return samples, failures, metadata, statements

    samples, failures, metadata, sql = e.call(measure)
    ordered = sorted(samples)
    metrics = {
        "warmup": 100,
        "measurements": len(samples),
        "p50_ms": statistics.median(samples),
        "p95_ms": ordered[math.ceil(len(samples) * 0.95) - 1],
        "peak_ms": max(samples),
        "error_rate": failures / len(samples),
        "chunks": count,
        "dimension": 384,
        "cpus_visible": os.cpu_count(),
        "pg": metadata,
        "sql_without_parameters": sql,
        "samples_ms": samples,
        "scope": "本机真实PG数据库调用；不含外部网络",
    }
    c.note("观察", metrics)
    c.equal(failures, 0, "100次测量无错误")
    c.check(metrics["p95_ms"] <= 1000, "数据库召回p95不超过1秒", metrics["p95_ms"])
    c.check(
        bool(sql) and "MATERIALIZED" in sql[0] and "LIMIT" in sql[0],
        "测量生产范围物化及数据库Top-K SQL",
    )


def eval008(c):
    # EVAL_008：已知延迟校验计量边界；独立观测每阶段，不代填产品duration。
    from harness.transport_fixtures import ControlledPort

    from backend.application import parse_jobs, retrieval, session_execution
    from backend.workers.handlers import index_build_handler

    e = c.environment()
    samples = {
        name: []
        for name in (
            "解析",
            "切片",
            "文档向量",
            "query向量",
            "数据库召回",
            "rerank",
            "增强",
            "生成",
        )
    }
    errors = dict.fromkeys(samples, 0)
    delay_seconds = 0.02

    async def measured(name, operation, *args, **kwargs):
        started = time.perf_counter()
        try:
            await asyncio.sleep(delay_seconds)
            return await operation(*args, **kwargs)
        except BaseException:
            errors[name] += 1
            raise
        finally:
            samples[name].append((time.perf_counter() - started) * 1000)

    def wrap(name, operation):
        async def observed(*args, **kwargs):
            return await measured(name, operation, *args, **kwargs)

        return observed

    original_embed = ControlledPort.embed

    async def embed(self, texts, *, purpose="document"):
        return await measured(
            "文档向量" if purpose == "document" else "query向量",
            original_embed,
            self,
            texts,
            purpose=purpose,
        )

    model_factory = session_execution.provider_from_snapshot2

    class MeasuredModel:
        def __init__(self, provider):
            self.provider = provider

        async def stream_request(self, request):
            # 异步流必须覆盖到最后一个delta及正常结束，不能只测创建generator。
            started = time.perf_counter()
            try:
                await asyncio.sleep(delay_seconds)
                async for delta in self.provider.stream_request(request):
                    yield delta
            except BaseException:
                errors["生成"] += 1
                raise
            finally:
                samples["生成"].append((time.perf_counter() - started) * 1000)

    walls = {name: [] for name in ("入库", "诊断", "Run", "整链")}
    with ExitStack() as stack:
        for owner, field, replacement in (
            (parse_jobs, "isolated", wrap("解析", parse_jobs.isolated)),
            (index_build_handler, "isolated", wrap("切片", index_build_handler.isolated)),
            (ControlledPort, "embed", embed),
            (VectorSearch, "search", wrap("数据库召回", VectorSearch.search)),
            (ControlledPort, "rank", wrap("rerank", ControlledPort.rank)),
            (retrieval, "assemble_evidence", wrap("增强", retrieval.assemble_evidence)),
            (
                session_execution,
                "provider_from_snapshot2",
                lambda p: MeasuredModel(model_factory(p)),
            ),
        ):
            stack.enter_context(patch.object(owner, field, replacement))
        for iteration in range(3):
            chain_start = time.perf_counter()
            for name, operation in (
                (
                    "入库",
                    lambda iteration=iteration: e.upload(
                        raw=f"ALPHA code is 37. Sample {iteration}.".encode()
                    ),
                ),
                ("诊断", lambda: e.diagnostic(overrides={"rerank_enabled": True})),
                ("Run", e.run),
            ):
                started = time.perf_counter()
                result = operation()
                walls[name].append((time.perf_counter() - started) * 1000)
                c.equal(
                    result["availability"]
                    if name == "入库"
                    else result["state" if name == "诊断" else "status"],
                    "ready" if name == "入库" else "succeeded",
                    "第" + str(iteration + 1) + "组" + name + "事实成功",
                )
            walls["整链"].append((time.perf_counter() - chain_start) * 1000)

    def metrics(values):
        ordered = sorted(values)
        return {
            "count": len(values),
            "samples_ms": values,
            "p50_ms": statistics.median(values),
            "p95_ms": ordered[math.ceil(len(values) * 0.95) - 1],
        }

    for name, values in samples.items():
        c.check(len(values) >= 3, "阶段被独立实际计量：" + name, len(values))
        c.check(
            min(values) >= delay_seconds * 1000 * 0.9,
            "阶段计量包含已知20ms延迟：" + name,
            min(values),
        )
        c.equal(errors[name], 0, "阶段计量无错误：" + name)
    rows = e.sql("SELECT timings_json FROM retrieval_executions ORDER BY created_at")
    c.note(
        "观察",
        {
            "工程阶段_ms": {
                name: {**metrics(values), "errors": errors[name]}
                for name, values in samples.items()
            },
            "工程聚合_ms": {name: metrics(values) for name, values in walls.items()},
            "已知注入延迟_ms": delay_seconds * 1000,
            "产品timings": rows,
            "产品尚无独立duration": ["解析", "文档向量", "生成"],
            "来源": (
                "生产阶段边界透明装饰器perf_counter；含20ms受控延迟，"
                "三组仅核计量器，不证明真实SLO或容量"
            ),
        },
    )
    c.check(all(len(values) == 3 for values in walls.values()), "三个独立流程均有整链及聚合采样")
    c.check(
        bool(rows) and all(isinstance(r["timings_json"], dict) for r in rows), "阶段结构可单独对照"
    )


CASES = {"EVAL_001": eval001, "EVAL_007": eval007, "EVAL_008": eval008}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
