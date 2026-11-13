"""CMP_001～014：本轮自建旧协议事实、真实PG迁移及一致备份恢复。"""

import hashlib
import os
import subprocess
from uuid import uuid4

from helpers.case_runner import run_category
from helpers.common import ROOT, load
from helpers.legacy_database import LegacyDatabase
from jsonschema import Draft202012Validator


def legacy_run(e, version=2, *, finish=True, **changes):
    thread = e.request(
        "POST", f"/api/v{version}/threads", expected=(201,), json={"title": "本轮旧协议夹具"}
    )
    payload = {
        "content": "ALPHA?",
        **(
            {"branch_id": thread["default_branch_id"], "expected_version": 0}
            if version == 2
            else {}
        ),
        **changes,
    }
    made = e.request(
        "POST",
        f"/api/v{version}/threads/{thread['thread_id']}/messages",
        expected=(201,),
        json=payload,
        headers={"Idempotency-Key": str(uuid4())},
    )
    if finish:
        e.finish(f"/api/v{version}/runs/" + made["run_id"], "status")
    return made


def cmp001(c):
    # CMP_001：原版本事实hash不变，读API后逐代严格校验。
    e = c.environment()
    e.upload()
    ids = [legacy_run(e, 1)["run_id"], legacy_run(e, 2)["run_id"], e.run()["run_id"]]
    before = e.sql("SELECT event_id,payload_json,schema_version FROM run_events ORDER BY event_id")
    schema = load(ROOT / "contracts/run_event_v3.json")
    for version, identity in enumerate(ids, 1):
        detail = e.request("GET", f"/api/v{version}/runs/" + identity)
        c.equal(detail["status"], "succeeded", "原协议正常读取")
        rows = e.request("GET", "/api/v3/runs/" + identity + "/events")["events"]
        c.check(bool(rows), "每代有Journal事实")
        for event in rows:
            c.equal(event["schema_version"], version, "版本不随产品版本重标")
            Draft202012Validator(schema).validate(event)
        c.check(True, "事件按三代严格联合契约通过", version)
    c.equal(
        e.sql("SELECT event_id,payload_json,schema_version FROM run_events ORDER BY event_id"),
        before,
        "读取未修改旧JSON/hash依据",
    )


def cmp003(c):
    # CMP_003：v1 txt/md完成发布后从v3正文/检索读取。
    e = c.environment()
    for extension in (".txt", ".md"):
        made = e.request(
            "POST",
            "/api/v1/documents",
            expected=(201,),
            files={"file": ("legacy" + extension, b"Legacy ALPHA 37", "text/plain")},
        )
        for _ in range(20):
            e.step()
            doc = e.request("GET", "/api/v3/documents/" + made["document_id"])
            if doc["availability"] == "ready":
                break
        c.equal(doc["availability"], "ready", "旧文本发布在新协议可用")
        execution = e.diagnostic(filters={"document_ids": [doc["document_id"]]})
        bundle = e.request("GET", "/api/v3/evidence-bundles/" + execution["bundle_ids"][0])
        c.equal(bundle["text"], "Legacy ALPHA 37", "旧正文可检索且原样")
        row = e.sql(
            "SELECT space_id,artifact_id FROM index_builds WHERE index_batch_id=:id",
            {"id": doc["active_index_batch_id"]},
        )[0]
        c.check(row["space_id"] and row["artifact_id"], "兼容发布补齐空间与Artifact")


def cmp004(c):
    # CMP_004：同Thread已有schema3，新旧读写入口边界。
    e = c.environment()
    run = e.run(enabled=False)
    thread = run["thread_id"]
    e.request("GET", "/api/v2/threads/" + thread, expected=(409,))
    e.request(
        "POST",
        f"/api/v2/threads/{thread}/messages",
        expected=(409,),
        json={"content": "old", "branch_id": run["branch_id"], "expected_version": 2},
        headers={"Idempotency-Key": str(uuid4())},
    )
    e.request("GET", "/api/v3/threads/" + thread)
    e.request("GET", f"/api/v2/threads/{thread}/branches")
    e.request("PATCH", "/api/v2/threads/" + thread, json={"title": "metadata still supported"})
    e.request("GET", "/api/v2/models")


def cmp005(c):
    # CMP_005：0007拒绝有效租约，过期后只结算遗留DOCX，不外发。
    with LegacyDatabase(c) as db:
        item = db.seed(".docx", lease=True)
        c.rejects(lambda: db.migrate("0007_rag_catalog_and_profiles"), error_types=(RuntimeError,))
        c.equal(db.sql("SELECT state FROM tasks")[0]["state"], "running", "拒绝不抢停旧租约")
        db.sql("UPDATE tasks SET lease_expires_at=now()-interval '1 second'")
        db.migrate("0007_rag_catalog_and_profiles")
        row = db.sql(
            "SELECT state,last_error_code FROM tasks WHERE task_id=:id", {"id": item["task_id"]}
        )[0]
        c.equal(
            (row["state"], row["last_error_code"]),
            ("failed", "DOCUMENT_WRITE_UPGRADE_REQUIRED"),
            "遗留DOCX明确升级终止",
        )


def cmp006(c):
    # CMP_006：非空旧库缺bootstrap不能猜空间；显式导入后每owner唯一归属。
    with LegacyDatabase(c) as db:
        db.seed()
        db.seed(owner="rag-test-owner-b")
        db.migrate("0007_rag_catalog_and_profiles")
        c.rejects(lambda: db.migrate("0008_rag_builds_and_vectors"), error_types=(RuntimeError,))
        db.upgrade()
        c.equal(
            db.sql("SELECT count(*) n FROM knowledge_bases WHERE is_default")[0]["n"],
            2,
            "每owner唯一默认库",
        )
        c.equal(
            db.sql("SELECT count(*) n FROM documents WHERE knowledge_base_id IS NULL")[0]["n"],
            0,
            "旧文档显式归属",
        )


def cmp007(c):
    # CMP_007：迁移隔离未知空间，不改向量数值。
    with LegacyDatabase(c) as db:
        db.seed()
        before = db.sql("SELECT embedding::text value FROM chunks")
        db.upgrade()
        c.equal(db.sql("SELECT embedding::text value FROM chunks"), before, "旧向量字节含义不变")
        c.equal(
            db.sql("SELECT provenance,space_id FROM index_builds")[0],
            {"provenance": "legacy_unknown", "space_id": None},
            "未知批次隔离",
        )
        c.equal(
            db.sql("SELECT legacy_unverified FROM chunks")[0]["legacy_unverified"],
            True,
            "不自动确认",
        )


def cmp008(c):
    # CMP_008：显式可信确认只接受归属/hash/原空间一致，不重算向量。
    with LegacyDatabase(c) as db:
        db.seed()
        db.upgrade()
        before = db.sql("SELECT embedding::text value FROM chunks")
        c.rejects(lambda: db.confirm(space_id="wrong"), error_types=(ValueError,))
        c.rejects(
            lambda: db.confirm(batches=[{**db.identity, "source_hash": "wrong"}]),
            error_types=(ValueError,),
        )
        c.equal(db.confirm()[0]["state"], "would_confirm", "默认仅预览")
        for change in ("provenance='new'", "provenance='legacy_verified'", "provenance='legacy_confirmed'"):
            c.rejects(lambda change=change: db.sql("UPDATE index_builds SET " + change))
        c.rejects(lambda: db.sql("UPDATE chunks SET legacy_unverified=false"))
        c.rejects(lambda: db.sql("UPDATE chunks SET text='forged'"))
        c.rejects(lambda: db.sql("UPDATE chunks SET index_batch_id='forged'"))

        from sqlalchemy.exc import DBAPIError

        try:
            confirmed = db.confirm(apply=True)
        except DBAPIError as exc:
            c.check(
                False,
                "生产确认工具应在真实PG正确完成空间关系更新",
                {
                    "SQLSTATE": getattr(exc.orig, "sqlstate", None),
                    "文件": "backend/tools/confirm_legacy_rag_space.py::confirm",
                },
            )
        c.equal(confirmed[0]["state"], "confirmed", "明确应用确认")
        c.equal(db.confirm(apply=True)[0]["state"], "already_confirmed", "重复幂等")
        c.equal(db.sql("SELECT embedding::text value FROM chunks"), before, "不重算旧向量")
        for change in ("provenance='new'", "provenance='legacy_unknown'"):
            c.rejects(lambda change=change: db.sql("UPDATE index_builds SET " + change))
        c.rejects(lambda: db.sql("UPDATE chunks SET legacy_unverified=true"))



def cmp009(c):
    # CMP_009：实际迁移建立旧引用保护，缺片段不猜补。
    with LegacyDatabase(c) as db:
        db.seed(citations=True)
        before = db.sql("SELECT citations_json FROM messages")
        db.upgrade()
        c.equal(
            sorted(
                r["availability"] for r in db.sql("SELECT availability FROM legacy_evidence_refs")
            ),
            ["available", "unavailable"],
            "现存与不可恢复分别标识",
        )
        c.equal(db.sql("SELECT citations_json FROM messages"), before, "不重写原引用")
        c.rejects(lambda: db.sql("DELETE FROM chunks"))


def cmp010(c):
    # CMP_010：真实四段迁移后重复产品升级工具，不覆盖配置/回填。
    with LegacyDatabase(c) as db:
        db.seed()
        db.upgrade()
        before = {
            t: db.sql(f"SELECT count(*) n FROM {t}")[0]["n"]
            for t in ("index_builds", "knowledge_bases", "embedding_profiles")
        }
        db.upgrade()
        c.equal(
            {t: db.sql(f"SELECT count(*) n FROM {t}")[0]["n"] for t in before},
            before,
            "重复升级无额外回填",
        )
        revision = db.sql("SELECT version_num FROM alembic_version")[0]["version_num"]
        c.equal(revision, "0011_rag_source_integrity", "迁移至正式0011")
        c.check(len(revision) <= 32, "Alembic revision长度合法")


def cmp011(c):
    # CMP_011：实际downgrade保护新事实，空结构可按允许路径回退。
    e = c.environment()
    e.upload()
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    engine = create_engine(e.url)
    try:
        with engine.begin() as conn:
            config = Config("alembic.ini")
            config.attributes["connection"] = conn
            c.rejects(
                lambda: command.downgrade(config, "0006_v2_run_guards"), error_types=(RuntimeError,)
            )
    finally:
        engine.dispose()
    c.equal(e.sql("SELECT count(*) n FROM parse_jobs")[0]["n"], 1, "拒绝降级未删新事实")
    with LegacyDatabase(c) as db:
        db.upgrade()
        db.migrate("0006_v2_run_guards", downgrade=True)
        c.equal(
            db.sql("SELECT version_num FROM alembic_version")[0]["version_num"],
            "0006_v2_run_guards",
            "纯结构回退完成",
        )


def cmp012(c):
    # CMP_012：本例旧PG+源文件一致备份，停写恢复，再迁移；新事实不在旧备份内。
    with LegacyDatabase(c) as db:
        db.seed(citations=True)
        before = db.sql("SELECT citations_json,content FROM messages")
        sources = {p.name: p.read_bytes() for p in db.settings.upload_path.iterdir()}
        dump = db.root / "before.dump"
        env = {**os.environ, "PGPASSWORD": db.url.password}
        common = ["-h", "postgres", "-U", "rag_test", "-d", db.url.database]
        made = subprocess.run(
            ["pg_dump", *common, "-Fc", "-f", str(dump)], env=env, capture_output=True, timeout=60
        )
        c.equal(made.returncode, 0, "实际pg_dump成功")
        dump_hash = hashlib.sha256(dump.read_bytes()).hexdigest()
        db.upgrade()
        from fastapi.testclient import TestClient

        from backend.app import create_app

        with TestClient(create_app(db.settings)) as client:
            made = client.post(
                "/api/v3/knowledge-bases",
                json={
                    "name": "备份后新增事实",
                    "embedding_profile_id": "mock-embedding",
                    "embedding_profile_version": 1,
                },
                headers={"Idempotency-Key": str(uuid4())},
            )
            c.equal(made.status_code, 201, "升级后经正式API生成不在旧备份内的新事实")
        # engine关闭后恢复到新建的专属同名数据库；从未对开发库执行。
        db.engine.dispose()
        db.admin.drop_database(db.key)
        db.admin.create_database(db.key)
        restored = subprocess.run(
            ["pg_restore", *common, "--exit-on-error", str(dump)],
            env=env,
            capture_output=True,
            timeout=60,
        )
        from helpers.evidence import redact

        c.note(
            "观察",
            {
                "恢复退出码": restored.returncode,
                "安全诊断": redact(restored.stderr.decode(errors="replace"))[:1200],
            },
        )
        c.equal(restored.returncode, 0, "实际pg_restore成功")
        c.equal(
            db.sql("SELECT citations_json,content FROM messages"), before, "旧消息及引用恢复一致"
        )
        c.equal(
            {p.name: p.read_bytes() for p in db.settings.upload_path.iterdir()},
            sources,
            "源文件与备份同一时点",
        )
        c.equal(
            db.sql("SELECT version_num FROM alembic_version")[0]["version_num"],
            "0006_v2_run_guards",
            "恢复为旧版本事实",
        )
        db.upgrade()
        c.note(
            "观察",
            {
                "dump_sha256": dump_hash,
                "镜像/源码身份": c.context["fingerprints"],
                "边界": "升级后确认事实不在旧备份；不声称无损回退",
            },
        )


def cmp013(c):
    # CMP_013：正式说明与严格DTO枚举一致，缺失位置不能伪造新枚举。
    import re
    from backend.api.schemas.v3.documents import Location

    schema = Location.model_json_schema()
    actual = schema["properties"]["quality"]["enum"]
    documentation = (ROOT / "docs" / "接口文档.md").read_text(encoding="utf-8")
    declared = re.search(r"quality=([a-z_|]+)", documentation).group(1).split("|")
    c.equal(set(declared), set(actual), "正式说明与Location质量枚举一致")
    sample = {"kind": "page", "origin": "source", "number": 1,
              "start_offset": 0, "end_offset": 1}
    for quality in actual:
        Location.model_validate({**sample, "quality": quality})
    c.rejects(lambda: Location.model_validate({**sample, "quality": "unavailable"}),
              error_types=(ValueError,))


def cmp014(c):
    # CMP_014：新Worker执行本轮创建的schema1/2在途Run，原冻结事实不改。
    e = c.environment()
    e.upload()
    for version in (1, 2):
        made = legacy_run(e, version, finish=False)
        before = e.sql("SELECT snapshot_json FROM runs WHERE run_id=:id", {"id": made["run_id"]})[0]
        e.finish(f"/api/v{version}/runs/" + made["run_id"], "status")
        c.equal(
            e.sql("SELECT snapshot_json FROM runs WHERE run_id=:id", {"id": made["run_id"]})[0],
            before,
            "旧快照不改",
        )
        c.equal(
            e.sql("SELECT count(*) n FROM tool_calls WHERE run_id=:id", {"id": made["run_id"]})[0][
                "n"
            ],
            0,
            "不补造新工具调用",
        )
        c.equal(
            e.sql("SELECT retrieval_view_id FROM runs WHERE run_id=:id", {"id": made["run_id"]})[0][
                "retrieval_view_id"
            ],
            None,
            "不补造View",
        )


def cmp002(c):
    # CMP_002：旧上传/重建先拒绝，v3登记的现有办公历史仍可读。
    e = c.environment()
    for extension in (".docx", ".pdf", ".xls", ".ppt"):
        response = e.client.post(
            "/api/v1/documents",
            files={"file": ("old" + extension, b"unused", "application/octet-stream")},
        )
        c.equal(
            response.status_code, 409 if extension == ".docx" else 415, "旧入口明确拒绝办公写入"
        )
    c.equal(e.sql("SELECT count(*) n FROM documents")[0]["n"], 0, "拒绝在新事实之前")
    from helpers.common import SUITE

    manifests = load(SUITE / "fixtures/manifest.json")
    c.check(bool(manifests), "本轮Office输入声明存在")
    # 旧DOCX历史由本轮专属迁移夹具构造，不冒充当前云端解析。
    with LegacyDatabase(c) as db:
        item = db.seed(".docx")
        db.upgrade()
        c.equal(
            db.sql(
                "SELECT filename FROM documents WHERE document_id=:id", {"id": item["document_id"]}
            )[0]["filename"],
            "legacy.docx",
            "迁移保留历史文档",
        )


CASES = {f"CMP_{i:03}": globals()[f"cmp{i:03}"] for i in range(1, 15)}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
