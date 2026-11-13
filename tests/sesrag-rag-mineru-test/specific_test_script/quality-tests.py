"""QLT_001～010及REAL_012：公开安全/契约/质量；每项实际执行并独立留证。"""

import ast
import copy
import json
import re
import subprocess
import time
from pathlib import Path

from helpers.case_runner import run_category
from helpers.common import ROOT, SUITE, digest, load
from helpers.evidence import redact
from jsonschema import Draft202012Validator


def qlt001(c):
    # QLT_001：真实API/Worker输出公开投影扫描；敏感哨兵不进入证据。
    e = c.environment()
    e.upload()
    run = e.run()
    detail = e.request("GET", "/api/v3/runs/" + run["run_id"])
    events = e.request("GET", f"/api/v3/runs/{run['run_id']}/events")
    profiles = e.request("GET", "/api/v3/rag/profiles")
    snapshot = e.sql("SELECT snapshot_json FROM runs WHERE run_id=:id", {"id": run["run_id"]})[0]
    public = json.dumps([detail, events, profiles, snapshot], ensure_ascii=False, default=str)
    for name in ("MINERU_API_KEY", "MODEL_API_KEY", "TEST_PASSWORD", "TEST_CONTROL_TOKEN"):
        import os

        secret = os.getenv(name)
        c.check(not secret or secret not in public, "公开投影不含运行凭据：" + name)
    c.check(
        not re.search(r"Bearer\s+\S+|https?://\S+Signature=|[A-Z]:\\", public),
        "API/事件/快照无敏感URL/Authorization/宿主路径",
    )
    c.note("观察", {"公开投影数量": 4, "公开内容sha256": digest(public), "全文Prompt": "未归档"})


def qlt002(c):
    # QLT_002：只读配置源边界；不导入或打印任何真实值。
    prepare = (SUITE / "helpers/prepare_runtime.py").read_text(encoding="utf8")
    gate = (SUITE / "helpers/live_preflight.py").read_text(encoding="utf8")
    build = (SUITE / "helpers/builds.py").read_text(encoding="utf8")
    templates = "\n".join(p.read_text(encoding="utf8") for p in (SUITE / "fixtures").glob("*.json"))
    c.check("runtime-inputs" in gate and "authorized" in gate, "真实配置来自显式私有输入及授权")
    c.check(
        not any(
            "docs/secret" in node.value.replace("\\", "/")
            for source in (prepare, gate)
            for call in ast.walk(ast.parse(source))
            if isinstance(call, ast.Call)
            for node in ast.walk(call)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ),
        "不扫描秘密文档",
    )
    c.check("--build-arg" not in build or "APP_IMAGE=" in build, "构建参数用途受限")
    c.check(
        not re.search(r"sk-[A-Za-z0-9]{12,}|Bearer [A-Za-z0-9]{20,}", templates),
        "JSON模板无真实Key形态",
    )
    c.note("观察", "真实环境存在性/镜像history由宿主工程准入另留证；本例未读取Key或外发")


def qlt003(c):
    # QLT_003：正式资源和事件契约正例及额外字段/错误版本负例。
    e = c.environment()
    doc = e.upload()
    run = e.run()
    resources = [
        ("document_v3.json", doc),
        ("run_v3.json", e.request("GET", "/api/v3/runs/" + run["run_id"])),
    ]
    events = e.request("GET", f"/api/v3/runs/{run['run_id']}/events")["events"]
    resources += [("run_event_v3.json", value) for value in events]
    for name, value in resources:
        validator = Draft202012Validator(load(ROOT / "contracts" / name))
        validator.validate(value)
        c.check(True, "正式正例严格验证：" + name)
        bad = {**value, "unexpected_private": "forbidden"}
        c.check(not validator.is_valid(bad), "额外字段负例拒绝：" + name)
    event = copy.deepcopy(events[0])
    event["schema_version"] = 99
    c.check(
        not Draft202012Validator(load(ROOT / "contracts/run_event_v3.json")).is_valid(event),
        "未知事件版本拒绝",
    )
    for filename in ("tool_rag_search_input_v1.json", "tool_rag_search_result_v2.json"):
        c.check(
            not Draft202012Validator(load(ROOT / "contracts" / filename)).is_valid(
                {"arbitrary": True}
            ),
            "工具任意参数拒绝",
        )


def qlt004(c):
    # QLT_004：各质量命令全部执行，记录各自输出，不能前一失败就漏后续。
    commands = [
        (["python", "-m", "backend.tools.export_rag_contracts", "--check"], "/app"),
        *[
            (["npm", "run", task], "/app/frontend")
            for task in ("check:api", "typecheck", "lint", "build")
        ],
    ]
    results = []
    for cmd, cwd in commands:
        started = time.perf_counter()
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)
        output = redact(r.stdout + r.stderr)
        target = c.report / ("quality-" + str(len(results)) + ".log")
        target.write_text(output, encoding="utf8")
        results.append(
            {
                "command": cmd,
                "exit": r.returncode,
                "duration_ms": (time.perf_counter() - started) * 1000,
                "log": target.name,
                "output_sha256": digest(output),
            }
        )
    c.note("观察", results)
    c.check(
        all(row["exit"] == 0 for row in results),
        "契约/生成类型/类型检查/Lint/构建全部通过",
        results,
    )


def qlt005(c):
    # QLT_005：真实浏览器运行事件解析器，与严格Schema负例对照。
    r = subprocess.run(
        [
            "node",
            "/suite/helpers/browser-cases.mjs",
            "--case",
            "QLT_005",
            "--origin",
            c.context["addresses"]["api"],
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    value = json.loads(r.stdout.strip().splitlines()[-1])
    c.note("观察", value)
    c.check(value["assertions"] > 0, "真实浏览器有具体拒绝断言")
    c.check(value["passed"], "严格契约非法事件在前端全部拒绝")


def qlt006(c):
    # QLT_006：AST导入边界＋替身契约；不宣称切片/增强是热切换Port。
    violations = []
    for path in (ROOT / "backend/domain").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                ("backend.infrastructure", "fastapi", "sqlalchemy", "httpx")
            ):
                violations.append(path.relative_to(ROOT).as_posix())
    c.equal(violations, [], "领域层不依赖厂商/ORM/HTTP")
    from backend.domain.ports.rag import (
        ArtifactNormalizer,
        EmbeddingPortV2,
        ParseGateway,
        RerankPort,
        VectorSearchPort,
    )

    c.equal(
        [
            name
            for cls, name in [
                (ParseGateway, "submit"),
                (ArtifactNormalizer, "normalize"),
                (EmbeddingPortV2, "embed"),
                (VectorSearchPort, "search"),
                (RerankPort, "rank"),
            ]
            if hasattr(cls, name)
        ],
        ["submit", "normalize", "embed", "search", "rank"],
        "五能力具备明确Port",
    )
    e = c.environment()
    e.upload()
    result = e.diagnostic(overrides={"rerank_enabled": True})
    c.equal(result["state"], "succeeded", "受控替身按共同契约装配完整链")
    c.note("观察", "切片/增强为独立函数；不是运行时可切换Port")


def qlt007(c):
    # QLT_007：同源内容+配置重复准备，比较范围/分数/语义身份而非随机UUID。
    e = c.environment()
    e.upload()
    a, b = e.diagnostic(), e.diagnostic()

    def comparable(row):
        return [(x["chunk_id"], x["dense_score"], x["rerank_score"]) for x in row["candidates"]]

    c.equal(comparable(a), comparable(b), "固定向量候选与分数可重复")
    left = [e.request("GET", "/api/v3/evidence-bundles/" + i) for i in a["bundle_ids"]]
    right = [e.request("GET", "/api/v3/evidence-bundles/" + i) for i in b["bundle_ids"]]
    c.equal(
        [(r["text"], r["index_batch_id"]) for r in left],
        [(r["text"], r["index_batch_id"]) for r in right],
        "拼接内容范围可重复",
    )


def qlt008(c):
    # QLT_008：每类稳定安全码和状态有中文投影，未知码保留安全兜底。
    e = c.environment()
    for filename, content in (("x.exe", b"invalid"), ("empty.txt", b"")):
        row = e.upload(raw=content, filename=filename, expected=(413, 415, 422), finish=False)
        c.check(
            isinstance(row.get("message"), str)
            and bool(re.search(r"[\u4e00-\u9fff]", row["message"])),
            "错误响应有中文说明",
            row.get("code"),
        )
    labels = (ROOT / "frontend/src/components/rag-labels.ts").read_text(encoding="utf8")
    for value in ("无可用证据", "已明确降级", "失败", "云端受理结果未知"):
        c.check(value in labels, "安全状态有中文词汇", value)
    c.check("labels[value] ?? value" in labels, "未知阶段保安全值而非成功")


def qlt009(c):
    # QLT_009：实际探测非目标入口，不新增任意工具/跨库/硬删除/公式执行能力。
    e = c.environment()
    doc = e.upload()
    for path, payload in (
        ("/api/v3/tools/execute", {"name": "shell", "command": "no"}),
        ("/api/v3/retrieval-executions", {"query": "x", "knowledge_base_ids": [e.base]}),
    ):
        e.request("POST", path, expected=(404, 405, 422), json=payload)
    e.request("DELETE", "/api/v3/documents/" + doc["document_id"], expected=(404, 405))
    e.request(
        "POST",
        "/api/v3/documents/" + doc["document_id"] + "/execute-formula",
        expected=(404, 405),
        json={},
    )
    e.request(
        "POST",
        "/api/v3/retrieval-executions",
        expected=(422,),
        json={"query": "x", "knowledge_base_id": e.base, "ann": True},
    )


def qlt010(c):
    # QLT_010：关闭MinerU健康不崩溃，本地txt/md和off Run仍可用。
    e = c.environment(mineru_enabled=False, mineru_api_key="")
    c.equal(e.client.get("/health/live").status_code, 200, "外部关闭不影响存活")
    for name in ("local.txt", "local.md"):
        c.equal(e.upload(filename=name)["availability"], "ready", "本地入库可用")
    c.equal(e.run(enabled=False)["status"], "succeeded", "关闭RAG生成路径可用")
    # 格式签名使用本轮只读固定PDF，配置不可用时不创建云任务。
    source = next(Path("/inputs").rglob("*.pdf"))
    response = e.upload(
        raw=source.read_bytes(), filename="office.pdf", finish=False, expected=(409,)
    )
    c.check(
        response.get("code")
        in {"PARSER_UNAVAILABLE", "MINERU_UNAVAILABLE", "MINERU_DISABLED", "PROFILE_UNAVAILABLE"},
        "办公能力明确不可用",
        response,
    )


def real012(c):
    # REAL_012：报告来源分层，拒绝把local或小探针包装成当前真实闭环。
    from helpers.protocol import validate_result

    c.equal(c.context["lane"], "local", "质量检查本身不是供应商真实测试")
    value = {
        "schema_version": 1,
        "run_id": c.context["run_id"],
        "category": "quality",
        "lane": "real",
        "cases": [],
    }
    c.rejects(lambda: validate_result(value, c.context, {"cases": []}, c.report))
    c.note(
        "观察",
        {
            "local": "仅受控协议/流程",
            "真实": "仅Real入口+正式API+当前run证据可证明",
            "未执行": "不能通过HTTP200或旧产物补造",
        },
    )


CASES = {**{f"QLT_{n:03}": globals()[f"qlt{n:03}"] for n in range(1, 11)}, "REAL_012": real012}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
