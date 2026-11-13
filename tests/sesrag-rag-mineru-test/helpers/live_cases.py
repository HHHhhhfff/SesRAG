"""真实用例仅走正式API/Worker；能力、hash和共享预算先于每次逻辑操作。"""

import hashlib
import time
from pathlib import Path
from uuid import uuid4

import httpx
from helpers.common import SUITE, load
from helpers.live_budget import LiveBudget


class LiveCase:
    def __init__(self, case, required):
        self.case = case
        available = set(case.context.get("real_capabilities", []))
        missing = set(required) - available
        if missing:
            case.block("本次真实范围未提供能力：" + ",".join(sorted(missing)))
        self.budget = LiveBudget()
        self.plan = self.budget.plan
        self.client = httpx.Client(
            base_url=case.context["addresses"]["api"], timeout=30, trust_env=False
        )
        self.profiles = load("/config/profiles.json")

    def reserve(self, kind, amount=1):
        try:
            self.budget.reserve(kind, amount)
        except ValueError as exc:
            self.case.block("真实逻辑预算不足或已到截止，禁止额外请求：" + str(exc))

    def request(self, method, path, expected=(200,), **kwargs):
        response = self.client.request(method, path, **kwargs)
        self.case.check(
            response.status_code in expected,
            "真实正式API状态码",
            {"path": path.split("?")[0], "status": response.status_code},
        )
        return response.json()

    def wait(self, path, field="state"):
        deadline = time.monotonic() + min(self.plan["budget"]["timeout_seconds"], 1100)
        while time.monotonic() < deadline:
            row = self.request("GET", path)
            if row[field] in {"succeeded", "failed", "cancelled"}:
                self.case.check(
                    row[field] == "succeeded",
                    "真实业务终态成功，未知提交不重提",
                    {
                        "状态": row[field],
                        "阶段": row.get("stage"),
                        "错误码": row.get("error_code", row.get("last_error_code")),
                    },
                )
                return row
            time.sleep(2)
        raise AssertionError("真实业务超过有界轮询时间；不自动重新提交")

    def base(self):
        if "embedding" not in self.case.context.get("real_capabilities", []):
            return self.request("GET", "/api/v3/knowledge-bases")["items"][0]["knowledge_base_id"]
        profile = next(
            p
            for p in self.profiles
            if p.get("kind") == "embedding" and p.get("config", {}).get("adapter_kind") == "bailian"
        )
        return self.request(
            "POST",
            "/api/v3/knowledge-bases",
            expected=(201,),
            json={
                "name": self.case.case_id + "-" + uuid4().hex[:8],
                "embedding_profile_id": profile["profile_id"],
                "embedding_profile_version": profile["version"],
            },
            headers={"Idempotency-Key": str(uuid4())},
        )["knowledge_base_id"]

    def input(self, extension, *, scanned=False):
        rows = [r for r in self.plan["files"] if Path(r["file"]).suffix.lower() == extension]
        expectations = load(SUITE / "fixtures/real-expectations.json")["inputs"]
        if extension == ".pdf":
            # 单样本也按独立hash元数据分型，文件名不证明扫描或文本PDF。
            rows = [r for r in rows if expectations.get(r["sha256"], {}).get("scanned") is scanned]
        if not rows:
            self.case.block(
                "缺少本次已授权且hash冻结的"
                + ("扫描" if scanned else "")
                + extension
                + "独立样本；不能用Mock或其它格式替代"
            )
        row = rows[0]
        expectation = expectations.get(row["sha256"])
        if not expectation:
            self.case.block(
                "已授权输入缺少独立内容/结构预期；须先补对应hash的样本断言，不能由返回结果生成预期"
            )
        self.expectation = expectation
        raw = self.budget.approved_input(row["file"])
        self.case.note(
            "准备",
            {
                "格式": extension,
                "sha256": row["sha256"],
                "输入字节": len(raw),
                "来源": "本轮私有授权清单",
            },
        )
        return raw, Path(row["file"]).name

    def upload(self, extension, *, scanned=False):
        raw, filename = self.input(extension, scanned=scanned)
        office = extension not in {".txt", ".md"}
        if office:
            self.reserve("cloud_jobs")
        if "embedding" in self.case.context.get("real_capabilities", []):
            # 与生产冻结的硬上限一致预留；产物未知不估算片数或退还未知调用预算。
            upper = 128
            if not office:
                upper = min(max(1, len(raw.decode("utf-8-sig"))), upper)
            self.reserve("document_chunks", upper)
        import json

        made = self.request(
            "POST",
            "/api/v3/documents",
            expected=(202,),
            data={
                "knowledge_base_id": self.base(),
                "chunker": json.dumps(
                    {
                        "max_chunks": upper
                        if "embedding" in self.case.context.get("real_capabilities", [])
                        else 128
                    }
                ),
                "parse": json.dumps(
                    {"cloud_consent": True, "consent_version": "mineru-office-outbound-v1"}
                    if office
                    else {}
                ),
            },
            files={"file": (filename, raw, "application/octet-stream")},
            headers={"Idempotency-Key": self.case.case_id + "-" + str(uuid4())},
        )
        batch = made["latest_build"]["index_batch_id"]
        if "embedding" in self.case.context.get("real_capabilities", []):
            self.wait("/api/v3/index-builds/" + batch)
        else:
            # 仅解析能力补证：只判ParseJob成功，后续Mock索引不能成为真实Embedding证据。
            deadline = time.monotonic() + 1100
            while time.monotonic() < deadline:
                build = self.request("GET", "/api/v3/index-builds/" + batch)
                parse = build.get("parse") or {}
                if parse.get("state") in {"succeeded", "failed", "cancelled"}:
                    self.case.check(
                        parse["state"] == "succeeded",
                        "本轮真实MinerU解析终态",
                        {
                            "状态": parse["state"],
                            "阶段": parse.get("stage"),
                            "错误码": parse.get("error_code", build.get("error_code")),
                            "远端结果": parse.get("remote_outcome"),
                        },
                    )
                    break
                time.sleep(2)
            else:
                raise AssertionError("真实解析等待超时；不创建新云作业")
        build = self.request("GET", "/api/v3/index-builds/" + batch)
        self.case.check(
            bool(build.get("parse", {}).get("artifact_id")), "真实返回已归一化为非空Artifact身份"
        )
        from helpers.fixture_admin import FixtureAdmin
        from sqlalchemy import create_engine, text

        # 只读本project真实产物核验，不向供应商直调，也不预写成功事实。
        engine = create_engine(FixtureAdmin().url)
        try:
            with engine.connect() as conn:
                artifact = (
                    conn.execute(
                        text("SELECT text,text_hash FROM parsed_artifacts WHERE artifact_id=:id"),
                        {"id": build["parse"]["artifact_id"]},
                    )
                    .mappings()
                    .one()
                )
                blocks = (
                    conn.execute(
                        text(
                            "SELECT kind,start_offset,end_offset FROM parsed_blocks "
                            "WHERE artifact_id=:id ORDER BY seq"
                        ),
                        {"id": build["parse"]["artifact_id"]},
                    )
                    .mappings()
                    .all()
                )
        finally:
            engine.dispose()
        from helpers.source_annotations import bind_source

        annotations = load(SUITE / "fixtures/source-annotations.json")
        source_sha = hashlib.sha256(raw).hexdigest()
        if any(row["source_sha256"] == source_sha for row in annotations["sources"]):
            from helpers.common import write

            try:
                binding = {
                    "status": "bound",
                    **bind_source(annotations, source_sha, artifact["text"], artifact["text_hash"]),
                }
            except ValueError as exc:
                # 金标补充资料不能重写原格式用例目标；失败明确归档，不冒报已绑定。
                binding = {
                    "status": "unbound",
                    "source_sha256": source_sha,
                    "artifact_sha256": artifact["text_hash"],
                    "error": str(exc),
                    "questions": [],
                }
            write(self.case.report / (self.case.case_id + "-annotation-binding.json"), binding)
            self.case.note(
                "观察",
                {
                    "金标绑定状态": binding["status"],
                    "金标绑定题数": len(binding["questions"]),
                    "error": binding.get("error"),
                },
            )
        for expected in self.expectation["contains"]:
            self.case.check(
                expected.casefold() in artifact["text"].casefold(),
                "独立源样本内容确实返回",
                expected,
            )
        self.case.check(
            len(blocks) >= self.expectation["minimum_blocks"],
            "返回可用于文本RAG的结构块",
            len(blocks),
        )
        if self.expectation["expected_table"]:
            self.case.check(any(row["kind"] == "table" for row in blocks), "表格样本保留表格结构")
        self.case.note(
            "观察",
            {
                "产物text_hash": artifact["text_hash"],
                "结构类型": sorted({b["kind"] for b in blocks}),
                "全文": "不归档",
            },
        )
        self.case.note(
            "观察",
            {
                "batch": batch,
                "parse": build.get("parse"),
                "scope": "真实解析；Embedding仅在显式所选时计真实",
            },
        )
        return made

    def close(self):
        self.client.close()
