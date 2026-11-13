"""LIF_001～010：真实PG引用与生产GC；仅作用于本例专属数据库和目录。"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from helpers.case_runner import run_category

from backend.application.rag_capacity import BUILD_RESERVE, storage_usage
from backend.application.rag_gc import collect
from backend.config import Settings
from backend.db.models import utc_now


def gc(e, *, days=2, apply=False, at=None):
    now = at or utc_now() + timedelta(days=days)
    with (
        patch("backend.application.rag_gc.utc_now", return_value=now),
        patch("backend.application.rag_retention.utc_now", return_value=now),
    ):
        return e.call(collect, e.app.state.session_factory, e.settings, apply=apply)


def rebuild(e, doc, **body):
    build = e.request(
        "POST",
        f"/api/v3/documents/{doc['document_id']}/index-builds",
        expected=(202,),
        json=body,
        headers={"Idempotency-Key": str(uuid4())},
    )
    return e.finish("/api/v3/index-builds/" + build["index_batch_id"])


def pair(e):
    doc = e.upload()
    new = rebuild(e, doc)
    return doc, doc["active_index_batch_id"], new["index_batch_id"]


def snapshot(e):
    return {
        name: e.sql(f"SELECT count(*) n FROM {name}")[0]["n"]
        for name in ("documents", "index_builds", "chunks", "parsed_artifacts", "parse_jobs")
    }


def lif001(c):
    # LIF_001：软预算和磁盘拒绝独立观察，不将估算称为文件系统硬配额。
    e = c.environment()
    e.upload()

    async def usage():
        async with e.app.state.session_factory() as s:
            return await storage_usage(s, e.settings)

    measured = e.call(usage)
    c.check(measured["estimated_persistent_bytes"] > 0, "源/文本/向量进入估算", measured)
    c.note(
        "观察",
        {"本例目录实际字节": sum(p.stat().st_size for p in e.directory.rglob("*") if p.is_file())},
    )
    e.settings.rag_storage_budget_bytes = 1
    e.upload(expected=(507,), finish=False)
    e.request(
        "POST",
        "/api/v3/retrieval-executions",
        expected=(507,),
        json={"knowledge_base_id": e.base, "query": "ALPHA"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    e.settings.rag_storage_budget_bytes = 8 * 1024**3
    with patch("backend.application.rag_capacity.shutil.disk_usage", return_value=(100, 99, 1)):
        # 使用具名结果以符合disk_usage的正式free接口。
        from collections import namedtuple

        disk = namedtuple("Disk", "total used free")
        with patch(
            "backend.application.rag_capacity.shutil.disk_usage", return_value=disk(100, 99, 1)
        ):
            e.upload(expected=(507,), finish=False)
    c.equal(
        e.sql("SELECT count(*) n FROM tasks WHERE state='queued'")[0]["n"],
        0,
        "拒绝不遗留可运行任务",
    )


def lif002(c):
    # LIF_002：两个独立请求竞争PG预算锁，最多一次预留成功。
    e = c.environment()
    e.settings.rag_storage_budget_bytes = BUILD_RESERVE + 1024**2

    def send(i):
        return e.client.post(
            "/api/v3/documents",
            data={"knowledge_base_id": e.base},
            files={"file": (f"race-{i}.txt", b"ALPHA", "text/plain")},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        c.equal(sorted(pool.map(send, range(2))), [202, 507], "预算不可双放")
    build = e.sql("SELECT index_batch_id FROM index_builds")[0]["index_batch_id"]
    e.finish("/api/v3/index-builds/" + build)
    c.equal(
        e.sql("SELECT count(*) n FROM index_builds WHERE state IN ('queued','waiting','building')")[
            0
        ]["n"],
        0,
        "终态释放活动预留",
    )
    c.rejects(
        lambda: Settings(rag_tmp_budget_bytes=384 * 1024**2 - 1, _env_file=None),
        error_types=(ValueError,),
    )


def lif003(c):
    # LIF_003：通过Run形成View/Bundle/ContextEvidence/Citation保护旧批次。
    e = c.environment()
    doc = e.upload()
    execution = e.diagnostic()
    bundle = e.request("GET", "/api/v3/evidence-bundles/" + execution["bundle_ids"][0])
    e.run()
    rebuild(e, doc)
    result = gc(e, apply=True)
    c.check(
        any(
            r.get("index_batch_id") == doc["active_index_batch_id"] and r["action"] == "protected"
            for r in result["resources"]
        ),
        "历史引用批次受保护",
        result,
    )
    c.equal(
        e.request("GET", "/api/v3/evidence-bundles/" + bundle["bundle_id"]),
        bundle,
        "GC后正文/hash仍一致",
    )
    c.check(
        e.sql("SELECT count(*) n FROM context_evidence_ranges")[0]["n"] > 0, "上下文范围真实落库"
    )


def lif004(c):
    # LIF_004：以固定时钟验证创建年龄的严格边界；不修改成功批次不可变事实。
    e = c.environment()
    _, old, _ = pair(e)
    created = e.sql("SELECT created_at FROM index_builds WHERE index_batch_id=:id", {"id": old})[0][
        "created_at"
    ]
    exact = gc(e, at=created + timedelta(hours=24))
    c.check(not any(r.get("index_batch_id") == old for r in exact["resources"]), "恰24h不清理")
    after = gc(e, at=created + timedelta(hours=24, microseconds=1))
    c.check(
        any(
            r.get("index_batch_id") == old and r["action"] == "would_delete"
            for r in after["resources"]
        ),
        "严格超过24h可计划回收",
    )
    active = e.upload(finish=False)
    c.check(
        not any(
            r.get("index_batch_id") == active["latest_build"]["index_batch_id"]
            and r["action"] == "delete"
            for r in gc(e, apply=True)["resources"]
        ),
        "活动构建受保护",
    )
    c.check(e.sql("SELECT count(*) n FROM parse_jobs")[0]["n"] > 0, "保留Job与源hash事实")


def lif005(c):
    # LIF_005：dry-run无副作用、apply与预览同规则且幂等，源文件不删。
    e = c.environment()
    _, old, _ = pair(e)
    before = snapshot(e)
    sources = {p.name: p.read_bytes() for p in Path(e.settings.upload_dir).iterdir() if p.is_file()}
    plan = gc(e)
    c.equal(snapshot(e), before, "预览不修改数据库")
    c.check(
        any(
            r.get("index_batch_id") == old and r["action"] == "would_delete"
            for r in plan["resources"]
        ),
        "预览含无引用旧批次",
    )
    gc(e, apply=True)
    c.equal(
        e.sql("SELECT count(*) n FROM index_builds WHERE index_batch_id=:id", {"id": old})[0]["n"],
        0,
        "apply实际删除计划批次",
    )
    after = snapshot(e)
    gc(e, apply=True)
    c.equal(snapshot(e), after, "重复执行幂等")
    c.equal(
        {p.name: p.read_bytes() for p in Path(e.settings.upload_dir).iterdir() if p.is_file()},
        sources,
        "上传源未被业务GC删除",
    )


def lif006(c):
    # LIF_006：真实连接交错GC和View冻结，任何结果均不得悬空。
    e = c.environment()
    pair(e)
    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(gc, e, apply=True)
        b = pool.submit(e.diagnostic)
        a.result(timeout=30)
        execution = b.result(timeout=30)
    c.equal(execution["state"], "succeeded", "竞争有界结束")
    c.equal(
        e.sql(
            (
                "SELECT count(*) n FROM retrieval_view_items v LEFT JOIN index_bui"
                "lds b ON b.index_batch_id=v.index_batch_id WHERE b.index_batch_id"
                " IS NULL"
            )
        )[0]["n"],
        0,
        "无悬空View",
    )
    c.equal(
        e.sql(
            (
                "SELECT count(*) n FROM evidence_components e LEFT JOIN chunks c O"
                "N c.chunk_id=e.chunk_id WHERE c.chunk_id IS NULL"
            )
        )[0]["n"],
        0,
        "无悬空组件",
    )


def lif007(c):
    # LIF_007：仅单层普通陈旧文件可删，活动key、链接、目录及根外哨兵保护。
    e = c.environment()
    e.upload(finish=False)
    root = Path(e.settings.rag_tmp_dir)
    root.mkdir(exist_ok=True, parents=True)
    old = root / "old.bin"
    old.write_bytes(b"old")
    keep = root / "active.bin"
    keep.write_bytes(b"active")
    outside = e.directory / "outside.bin"
    outside.write_bytes(b"sentinel")
    link = root / "link.bin"
    link.symlink_to(outside)
    folder = root / "sub"
    folder.mkdir()
    (folder / "nested.bin").write_bytes(b"nested")
    for p in (old, keep):
        os.utime(p, (1, 1))
    e.sql("UPDATE parse_jobs SET private_state_key='active.bin'")
    gc(e, apply=True)
    c.check(not old.exists(), "仅陈旧普通文件删除")
    c.check(
        keep.exists() and link.is_symlink() and (folder / "nested.bin").exists(),
        "活动/链接/嵌套保护",
    )
    c.equal(outside.read_bytes(), b"sentinel", "根外哨兵不变")


def lif008(c):
    # LIF_008：七天按创建时点，只删除独立终态诊断，不删除Run视图。
    e = c.environment()
    e.upload()
    diagnostic = e.diagnostic()
    run = e.run()
    created = e.sql(
        "SELECT created_at FROM retrieval_executions WHERE execution_id=:id",
        {"id": diagnostic["execution_id"]},
    )[0]["created_at"]
    gc(e, at=created + timedelta(days=7), apply=True)
    e.request("GET", "/api/v3/retrieval-executions/" + diagnostic["execution_id"])
    gc(e, at=created + timedelta(days=7, microseconds=1), apply=True)
    e.request("GET", "/api/v3/retrieval-executions/" + diagnostic["execution_id"], expected=(410,))
    c.check(
        e.sql("SELECT count(*) n FROM runs WHERE retrieval_view_id IS NOT NULL")[0]["n"] > 0,
        "Run视图不被诊断保留策略清理",
    )
    e.request("GET", "/api/v3/runs/" + run["run_id"])


def lif009(c):
    # LIF_009：原owner三十天410，其他owner始终404，重复清理不续墓碑。
    e = c.environment()
    e.upload()
    item = e.diagnostic()
    now = utc_now() + timedelta(days=8)
    gc(e, at=now, apply=True)
    paths = [
        "/api/v3/retrieval-executions/" + item["execution_id"],
        "/api/v3/evidence-bundles/" + item["bundle_ids"][0],
    ]
    with patch("backend.application.rag_retention.utc_now", return_value=now):
        for path in paths:
            e.request("GET", path, expected=(410,))
    before = e.sql("SELECT resource_id,created_at FROM rag_gc_records ORDER BY resource_id")
    gc(e, at=now, apply=True)
    c.equal(
        e.sql("SELECT resource_id,created_at FROM rag_gc_records ORDER BY resource_id"),
        before,
        "墓碑不续期",
    )
    e.settings.owner_id = "rag-test-owner-b"
    for path in paths:
        e.request("GET", path, expected=(404,))
    e.settings.owner_id = "rag-test-owner-a"
    with patch("backend.application.rag_retention.utc_now", return_value=now + timedelta(days=31)):
        for path in paths:
            e.request("GET", path, expected=(404,))


def lif010(c):
    # LIF_010：GC清产物后，相同合法路线必须重新解析而非复用空artifact。
    import copy

    from helpers.common import SUITE, load

    e = c.environment()
    doc = e.upload()
    old_job = doc["latest_build"]["parse"]["parse_job_id"]
    profile = copy.deepcopy(
        next(
            r
            for r in load(SUITE / "fixtures/profiles.local.json")
            if r["profile_id"] == "local-text"
        )
    )
    profile["version"] = 2
    profile["config"]["parse_timeout"] = 121
    e.import_profiles([profile])
    rebuild(e, doc, parse={"parser_profile_id": "local-text", "parser_profile_version": 2})
    gc(e, apply=True)
    c.equal(
        e.sql("SELECT artifact_id FROM parse_jobs WHERE parse_job_id=:id", {"id": old_job})[0][
            "artifact_id"
        ],
        None,
        "旧产物回收且Job摘要保留",
    )
    built = rebuild(e, doc, parse={"parser_profile_id": "local-text", "parser_profile_version": 1})
    c.check(
        built["parse"]["parse_job_id"] != old_job and built["parse"]["artifact_id"],
        "不复用空产物，创建新解析",
    )


CASES = {f"LIF_{i:03}": globals()[f"lif{i:03}"] for i in range(1, 11)}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
