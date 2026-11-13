"""MIN恢复/终态与PAR出站/验包安全；每个编号独立判定。"""

import asyncio
import base64
import io
import json
import tempfile
import zipfile
from unittest.mock import AsyncMock, patch

import httpx
from helpers.case_runner import run_category

from backend.config import Settings
from backend.infrastructure.rag.artifact_store import ArtifactStore
from backend.infrastructure.rag.download_safety import PublicNetworkBackend, SafeHTTP
from backend.infrastructure.rag.mineru_client import MinerUClient
from backend.infrastructure.rag.mineru_outputs import normalize_package


def package(text="Body ALPHA 37", extra=()):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_STORED) as archive:
        if text is not None:
            archive.writestr("full.md", text)
        for name, value in extra:
            archive.writestr(name, value)
    return stream.getvalue()


def job():
    from helpers.common import SUITE, load

    config = next(
        r["config"]
        for r in load(SUITE / "fixtures/profiles.local.json")
        if r["profile_id"] == "mineru-office"
    )
    return {
        "parse_job_id": "job-test",
        "filename": "x.pdf",
        "config": {
            "is_ocr": False,
            "model_version": "vlm",
            "enable_table": True,
            "enable_formula": True,
            "language": "ch",
            **config,
        },
    }


def protocol(handler):
    return MinerUClient(
        Settings(
            _env_file=None,
            mineru_api_key="dummy-protocol",
            mineru_storage_host_allowlist="storage.test",
        ),
        transport=httpx.MockTransport(handler),
    )


HANDLE = {
    "batch_id": "batch",
    "filename": "x.pdf",
    "parse_job_id": "job-test",
    "upload_url": "https://storage.test/input",
}


def office(c):
    e = c.environment()
    doc = e.upload(raw=b"%PDF-1.7\nsynthetic\n%%EOF", filename="x.pdf", finish=False)
    return (
        e,
        doc,
        doc["latest_build"]["parse"]["parse_job_id"],
        doc["latest_build"]["index_batch_id"],
    )


def min001(c):
    # MIN_001：精准文件URL申请，HTTP和业务code同时检查。
    seen = []

    def response(request):
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"batch_id": "batch", "file_urls": ["https://storage.test/input"]},
            },
        )

    result = asyncio.run(protocol(response).submit(job()))
    c.equal(result["batch_id"], "batch", "保存远端工作身份")
    c.equal(seen[0][:2], ("POST", "/api/v4/file-urls/batch"), "精准API固定路径")
    c.equal(seen[0][2]["files"][0]["data_id"], "job-test", "本地Job作为文件身份")
    for body in (
        {"code": 1, "data": {}},
        {"code": 0, "data": {}},
        {"code": 0, "data": {"batch_id": "b", "file_urls": []}},
    ):
        c.rejects(
            lambda body=body: asyncio.run(
                protocol(lambda _, body=body: httpx.Response(200, json=body)).submit(job())
            )
        )


def min002(c):
    # MIN_002：原件PUT不带API Bearer，随后只查询原batch。
    requests = []

    def response(request):
        requests.append(request)
        if request.method == "PUT":
            return httpx.Response(204)
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "extract_result": [
                        {"data_id": "job-test", "file_name": "x.pdf", "state": "running"}
                    ]
                },
            },
        )

    gateway = protocol(response)
    asyncio.run(gateway.upload(b"original-source", HANDLE))
    asyncio.run(gateway.poll(HANDLE))
    c.equal(requests[0].content, b"original-source", "原字节PUT")
    c.check("authorization" not in requests[0].headers, "存储PUT无API Bearer")
    c.equal(requests[1].url.path, "/api/v4/extract-results/batch/batch", "只轮询原batch")


def min003(c):
    # MIN_003：错文件/ID/条数/状态均不得发布为当前文档。
    valid = {"data_id": "job-test", "file_name": "x.pdf", "state": "running"}
    for rows in (
        [],
        [valid, valid],
        [{**valid, "data_id": "other"}],
        [{**valid, "file_name": "other"}],
        [{**valid, "state": "unknown"}],
    ):
        c.rejects(
            lambda rows=rows: asyncio.run(
                protocol(
                    lambda _, rows=rows: httpx.Response(
                        200, json={"code": 0, "data": {"extract_result": rows}}
                    )
                ).poll(HANDLE)
            ),
            codes={"MINERU_OUTPUT_UNSUPPORTED"},
        )


def min004(c):
    # MIN_004：所有远端状态和未知进度安全投影。
    for state in ("waiting-file", "pending", "running", "converting", "done", "failed"):
        row = {
            "data_id": "job-test",
            "file_name": "x.pdf",
            "state": state,
            "full_zip_url": "https://storage.test/output",
            "err_msg": "private-upstream",
        }
        value = asyncio.run(
            protocol(
                lambda _, row=row: httpx.Response(
                    200, json={"code": 0, "data": {"extract_result": [row]}}
                )
            ).poll(HANDLE)
        )
        c.equal(value["state"], state, "远端状态不伪造")
        c.check(
            "progress" not in value and "private-upstream" not in str(value),
            "未知页数不填0且清洗错误正文",
        )


def min005(c):
    # MIN_005：done后下载/切片/向量/发布各阶段仍非active。
    e, doc, identity, batch = office(c)
    for _ in range(12):
        row = e.request("GET", "/api/v3/index-builds/" + batch)
        if row["parse"]["stage"] == "downloading":
            break
        e.step()
    c.equal(row["parse"]["stage"], "downloading", "远端done仅到下载阶段")
    for stage in (None, "chunk", "embed", "publish"):
        if stage:
            e.to_stage(doc, stage)
        c.equal(
            e.request("GET", "/api/v3/documents/" + doc["document_id"])["availability"],
            "none",
            "未发布不可检索",
        )


def min006(c):
    # MIN_006：POST未知不自动重提；submitting检查点恢复保守停止。
    e, doc, identity, batch = office(c)
    e.plan(identity, "mineru_submit", [{"fault": "connection"}])
    row = e.finish("/api/v3/index-builds/" + batch, successful=False)
    c.equal(row["error_code"], "MINERU_SUBMISSION_UNKNOWN", "未知提交明确终态")
    for _ in range(3):
        e.step()
    c.equal(e.observations(identity)["mineru_submit"]["count"], 1, "未知结果不重提")
    second = e.upload(raw=b"%PDF-1.7\n%%EOF", filename="second.pdf", finish=False)
    e.sql(
        "UPDATE parse_jobs SET stage='submitting' WHERE parse_job_id=:id",
        {"id": second["latest_build"]["parse"]["parse_job_id"]},
    )
    row = e.finish(
        "/api/v3/index-builds/" + second["latest_build"]["index_batch_id"], successful=False
    )
    c.equal(row["error_code"], "MINERU_SUBMISSION_UNKNOWN", "恢复不知提交结果时不重新申请")


def min007(c):
    # MIN_007：等待跨Worker新实例续跑同Job/远端工作。
    from backend.workers.runtime import WorkerRuntime

    e, doc, identity, batch = office(c)
    e.plan(
        identity,
        "mineru_poll",
        [
            {"state": "waiting-file"},
            {"state": "pending"},
            {"state": "running"},
            {"state": "converting"},
            {"state": "done"},
        ],
    )
    for _ in range(20):
        e.step(runtime=WorkerRuntime(e.settings, e.app.state.session_factory, e.app.state.notifier))
        row = e.request("GET", "/api/v3/index-builds/" + batch)
        if row["state"] == "succeeded":
            break
    c.equal(row["state"], "succeeded", "跨Worker恢复完成")
    c.equal(e.observations(identity)["mineru_submit"]["count"], 1, "恢复沿同一申请")
    c.equal(row["parse"]["parse_job_id"], identity, "Job身份不变")


def min008(c):
    # MIN_008：PUT应答丢失后先poll原batch，若已上传不再PUT。
    e, doc, identity, batch = office(c)
    e.plan(identity, "mineru_put", [{"fault": "connection"}])
    row = e.finish("/api/v3/index-builds/" + batch)
    calls = e.observations(identity)
    c.equal(calls["mineru_put"]["count"], 1, "已上传未知应答不重复PUT")
    c.equal(calls["mineru_submit"]["count"], 1, "不申请新batch")
    c.equal(row["parse"]["remote_outcome"], "completed", "最终已知完成")


def min009(c):
    # MIN_009：下载临时网络失败仍同batch恢复，成功产物唯一。
    e, doc, identity, batch = office(c)
    e.plan(identity, "mineru_download", [{"fault": "connection"}, {}])
    e.finish("/api/v3/index-builds/" + batch)
    calls = e.observations(identity)
    c.equal(calls["mineru_submit"]["count"], 1, "下载失败不重新解析")
    c.equal(calls["mineru_download"]["count"], 2, "同工作恢复下载")
    c.equal(e.sql("SELECT count(*) n FROM parsed_artifacts")[0]["n"], 1, "只有一个成功产物")


def min010(c):
    # MIN_010：waiting让出租约，不耗failure_count。
    e, doc, identity, batch = office(c)
    e.plan(identity, "mineru_poll", [{"state": "waiting-file"}, {"state": "pending"}])
    for _ in range(5):
        e.step()
    task = e.sql("SELECT state,attempt,failure_count,worker_id,lease_expires_at FROM tasks")[0]
    c.equal(task["state"], "waiting_external", "等待回排")
    c.equal(task["failure_count"], 0, "正常等待不耗错误预算")
    c.check(
        task["attempt"] > 3 and task["worker_id"] is None and task["lease_expires_at"] is None,
        "物理尝试增加且槽位释放",
    )


def min011(c):
    # MIN_011：Job deadline与轮询上限分别触发。
    e, doc, identity, batch = office(c)
    e.step()
    e.sql(
        "UPDATE parse_jobs SET parse_deadline=now()-interval '1 second' WHERE parse_job_id=:id",
        {"id": identity},
    )
    row = e.finish("/api/v3/index-builds/" + batch, successful=False)
    c.equal(row["error_code"], "MINERU_ATTEMPT_TIMEOUT", "Job总截止")
    new = e.upload(raw=b"%PDF-1.7\n%%EOF", filename="poll.pdf", finish=False)
    j = new["latest_build"]["parse"]["parse_job_id"]
    e.step()
    e.sql("UPDATE parse_jobs SET poll_count=60 WHERE parse_job_id=:id", {"id": j})
    e.plan(j, "mineru_poll", [{"state": "pending"}])
    row = e.finish(
        "/api/v3/index-builds/" + new["latest_build"]["index_batch_id"], successful=False
    )
    c.equal(row["error_code"], "MINERU_ATTEMPT_TIMEOUT", "轮询上限有界")


def min012(c):
    # MIN_012：安全请求临时故障有界耗尽，与waiting区分。
    e, doc, identity, batch = office(c)
    e.plan(identity, "mineru_poll", [{"status": 503}])
    row = e.finish("/api/v3/index-builds/" + batch, successful=False)
    c.equal(row["state"], "failed", "临时错误不能无限回排")
    c.check(1 <= e.observations(identity)["mineru_poll"]["count"] <= 3, "安全请求有限重试")


def min013(c):
    # MIN_013：认证、额度、确定failed错误码分开。
    for status, expected in (
        (401, "MINERU_AUTH_FAILED"),
        (403, "MINERU_AUTH_FAILED"),
        (429, "MINERU_QUOTA_EXHAUSTED"),
    ):
        c.rejects(lambda status=status: MinerUClient.checked(status, b"{}"), codes={expected})
    e, doc, identity, batch = office(c)
    e.plan(identity, "mineru_poll", [{"state": "failed"}])
    c.equal(
        e.finish("/api/v3/index-builds/" + batch, successful=False)["error_code"],
        "MINERU_PARSE_FAILED",
        "确定解析失败独立错误码",
    )


def min014(c):
    # MIN_014：明确failed与空产物不能本地兜底。
    e, doc, identity, batch = office(c)
    e.plan(identity, "mineru_download", [{"package": "empty"}])
    row = e.finish("/api/v3/index-builds/" + batch, successful=False)
    c.equal(row["error_code"], "MINERU_EMPTY_OUTPUT", "无有效文本失败")
    c.equal(row["parse"]["remote_outcome"], "completed", "远端已完成但本地无文本分开")
    c.equal(e.sql("SELECT count(*) n FROM parsed_artifacts")[0]["n"], 0, "无本地回退产物")


def min015(c):
    # MIN_015：未提交取消无远端副作用。
    e, doc, identity, batch = office(c)
    result = e.request("POST", "/api/v3/index-builds/" + batch + "/cancel", expected=(200, 202))
    c.equal(result["state"], "cancelled", "排队取消由服务端结算")
    e.step()
    c.equal(e.observations(identity)["mineru_submit"]["count"], 0, "取消前未提交则零申请")


def min016(c):
    # MIN_016：已提交取消仅本机终态，远端可能继续。
    e, doc, identity, batch = office(c)
    e.step()
    row = e.request("POST", "/api/v3/index-builds/" + batch + "/cancel", expected=(200, 202))
    c.equal(row["parse"]["remote_outcome"], "unknown_may_continue", "本机取消不冒称云端撤回")
    c.equal(row["state"], "cancelled", "本机取消事实")


def min017(c):
    # MIN_017：取消先/发布先两确定顺序，终态不可双写。
    e = c.environment()
    for cancel_first in (True, False):
        doc = e.upload(finish=False)
        build = e.to_stage(doc, "publish")
        if not cancel_first:
            e.step()
        e.request(
            "POST",
            "/api/v3/index-builds/" + build["index_batch_id"] + "/cancel",
            expected=(200, 202),
        )
        e.step()
        row = e.request("GET", "/api/v3/index-builds/" + build["index_batch_id"])
        c.equal(row["state"], "cancelled" if cancel_first else "succeeded", "终态先提交者胜")


def min018(c):
    # MIN_018：终态后迟到正常产物不能复活Job/Build。
    e, doc, identity, batch = office(c)
    e.step()
    e.request("POST", "/api/v3/index-builds/" + batch + "/cancel", expected=(200, 202))
    e.plan(identity, "mineru_poll", [{"state": "done"}])
    for _ in range(3):
        e.step()
    c.equal(
        e.request("GET", "/api/v3/index-builds/" + batch)["state"], "cancelled", "迟到done不复活"
    )
    c.equal(e.sql("SELECT count(*) n FROM parsed_artifacts")[0]["n"], 0, "不发布迟到产物")


def min019(c):
    # MIN_019：成功Artifact唯一，关系与来源hash由PG保护。
    e, doc, identity, batch = office(c)
    e.finish("/api/v3/index-builds/" + batch)
    c.equal(
        e.sql("SELECT count(*) n FROM parsed_artifacts WHERE parse_job_id=:id", {"id": identity})[
            0
        ]["n"],
        1,
        "同Job唯一成功产物",
    )
    c.rejects(lambda: e.sql("UPDATE parsed_artifacts SET source_hash='forged'"))
    c.rejects(lambda: e.sql("UPDATE index_builds SET artifact_id='forged'"))


def min020(c):
    # MIN_020：AES-GCM错误Key/篡改nonce密文/AAD均拒绝。
    with tempfile.TemporaryDirectory(dir="/data/scratch") as directory:
        key = base64.b64encode(b"x" * 32).decode()
        store = ArtifactStore(directory, key)
        store.save_state("state.bin", HANDLE)
        c.equal(store.load_state("state.bin"), HANDLE, "相同Key可恢复")
        c.check(b"https://" not in store.read("state.bin"), "磁盘状态非明文")
        c.rejects(
            lambda: ArtifactStore(directory, base64.b64encode(b"y" * 32).decode()).load_state(
                "state.bin"
            ),
            codes={"MINERU_STATE_UNAVAILABLE"},
        )
        raw = store.read("state.bin")
        for offset in (0, 15, len(raw) - 1):
            changed = bytearray(raw)
            changed[offset] ^= 1
            store.write("state.bin", changed)
            c.rejects(lambda: store.load_state("state.bin"), codes={"MINERU_STATE_UNAVAILABLE"})
        store.write("other.bin", raw)
        c.rejects(lambda: store.load_state("other.bin"), codes={"MINERU_STATE_UNAVAILABLE"})


def min021(c):
    # MIN_021：挂起HTTP真实async timeout，取消后协程不遗留。
    async def slow(request):
        await asyncio.sleep(10)
        return httpx.Response(200, content=b"ok")

    async def execute():
        http = SafeHTTP(["storage.test"], transport=httpx.MockTransport(slow))
        try:
            await http.request("GET", "https://storage.test/x", timeout=0.01)
        except Exception as exc:
            c.equal(exc.code, "UPSTREAM_TEMPORARY_UNAVAILABLE", "单次请求截止")
        task = asyncio.create_task(http.request("GET", "https://storage.test/x", timeout=1))
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        c.check(task.done(), "取消后请求已结束")

    asyncio.run(execute())


def min022(c):
    # MIN_022：保留完整观测目标，实际日志缺duration应失败而非假填。
    import logging

    from backend.workers import runtime as runtime_module

    e, doc, identity, batch = office(c)
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            try:
                records.append(json.loads(record.getMessage()))
            except (ValueError, TypeError):
                pass

    handler = Capture()
    logger = runtime_module.logger
    previous, previously_disabled = logger.level, logger.disabled
    # MIN_022：同进程Alembic迁移会禁用已有logger；只恢复观测，保留产品日志断言。
    logger.disabled = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        e.finish("/api/v3/index-builds/" + batch)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)
        logger.disabled = previously_disabled
    c.note(
        "观察",
        {
            "安全记录数": len(records),
            "已有字段": sorted(set().union(*(r.keys() for r in records))),
            "迁移后logger原禁用状态": previously_disabled,
        },
    )
    c.check(
        records
        and all(
            {
                "document_id",
                "parse_job_id",
                "index_batch_id",
                "task_id",
                "worker_id",
                "generation",
                "attempt",
                "run_id",
                "retrieval_execution_id",
                "error_code",
                "stage",
                "duration_ms",
            }
            <= r.keys()
            for r in records
        ),
        "完整阶段关联身份与耗时须有真实观测",
    )
    correlated = [r for r in records if r.get("index_batch_id") == batch]
    c.check(
        correlated
        and all(
            r["document_id"] == doc["document_id"]
            and r["parse_job_id"] == identity
            and isinstance(r["duration_ms"], (int, float))
            and r["duration_ms"] >= 0
            for r in correlated
        ),
        "构建日志须关联真实文档和解析身份，耗时为非负数",
    )
    c.check(
        {"parse", "chunk", "embed", "publish"}
        <= {r["stage"] for r in correlated if r["action"] == "stage"},
        "真实Worker必须覆盖解析、切片、向量和发布阶段边界",
    )


def par001(c):
    # PAR_001：URL白名单不会按上游返回自动扩大。
    http = SafeHTTP(["allowed.test"], transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    for url in (
        "http://allowed.test/a",
        "https://allowed.test:80/a",
        "https://u:p@allowed.test/a",
        "https://allowed.test/a#x",
        "https://other.test/a",
        "https://127.0.0.1/a",
    ):
        c.rejects(lambda url=url: http.validate(url), codes={"OUTBOUND_TARGET_UNSAFE"})
    http.validate("https://allowed.test:443/a")
    c.check(True, "精确HTTPS/443白名单正例")


def par002(c):
    # PAR_002：真实公网后端拒绝私网/混合DNS且连接已验证IP。
    async def exercise():
        backend = PublicNetworkBackend()
        loop = asyncio.get_running_loop()
        for ips in (
            ["127.0.0.1"],
            ["10.0.0.1"],
            ["169.254.169.254"],
            ["::1"],
            ["8.8.8.8", "192.168.1.1"],
        ):
            rows = [(None, None, None, None, (ip, 443)) for ip in ips]
            with patch.object(loop, "getaddrinfo", AsyncMock(return_value=rows)):
                try:
                    await backend.connect_tcp("allowed.test", 443)
                except Exception as exc:
                    c.equal(exc.code, "OUTBOUND_TARGET_UNSAFE", "拒绝私网或混合DNS")
                else:
                    c.check(False, "私网不能连接")
        with (
            patch.object(
                loop,
                "getaddrinfo",
                AsyncMock(return_value=[(None, None, None, None, ("8.8.8.8", 443))]),
            ),
            patch.object(backend.backend, "connect_tcp", AsyncMock(return_value="stream")) as tcp,
        ):
            c.equal(await backend.connect_tcp("allowed.test", 443), "stream", "连接已校验公网IP")
            c.equal(tcp.call_args.args[0], "8.8.8.8", "不再用host重新DNS连接")

    asyncio.run(exercise())


def par003(c):
    # PAR_003：跨origin去凭据，非GET跳转不重放，循环有界。
    seen = []

    def redirect(request):
        seen.append(request)
        return (
            httpx.Response(302, headers={"location": "https://b.test/final"})
            if request.url.host == "a.test"
            else httpx.Response(200, content=b"ok")
        )

    http = SafeHTTP(["a.test", "b.test"], transport=httpx.MockTransport(redirect))
    c.equal(
        asyncio.run(
            http.request("GET", "https://a.test/start", headers={"Authorization": "Bearer dummy"})
        )[0],
        200,
        "合法跳转",
    )
    c.check("authorization" not in seen[-1].headers, "跨origin不转发凭据")
    for method in ("POST", "PUT"):
        c.rejects(
            lambda method=method: asyncio.run(http.request(method, "https://a.test/start")),
            codes={"OUTBOUND_REDIRECT_UNSAFE"},
        )
    loop = SafeHTTP(
        ["a.test"],
        transport=httpx.MockTransport(lambda _: httpx.Response(302, headers={"location": "/loop"})),
    )
    c.rejects(
        lambda: asyncio.run(loop.request("GET", "https://a.test/loop")),
        codes={"OUTBOUND_REDIRECT_UNSAFE"},
    )


def par004(c):
    # PAR_004：实际累计字节，等于/超过100MiB；不信任Content-Length。
    class Blocks(httpx.AsyncByteStream):
        def __init__(self, count):
            self.count = count

        async def __aiter__(self):
            remaining = self.count
            while remaining:
                size = min(1024**2, remaining)
                yield b"a" * size
                remaining -= size

    for size in (100 * 1024**2, 100 * 1024**2 + 1):
        http = SafeHTTP(
            ["a.test"],
            transport=httpx.MockTransport(
                lambda _, size=size: httpx.Response(
                    200, headers={"content-length": "1"}, stream=Blocks(size)
                )
            ),
        )
        if size % (1024**2) == 0:
            c.equal(
                len(
                    asyncio.run(http.request("GET", "https://a.test/x", max_bytes=100 * 1024**2))[1]
                ),
                size,
                "等于下载上限允许",
            )
        else:
            c.rejects(
                lambda http=http: asyncio.run(
                    http.request("GET", "https://a.test/x", max_bytes=100 * 1024**2)
                ),
                codes={"UPSTREAM_RESPONSE_LIMIT"},
            )


def par005(c):
    # PAR_005：逃逸/绝对/符号链接/重复/加密/嵌套包拒绝。
    for name in ("../escape", "/absolute", "nested.zip", "FULL.md"):
        c.rejects(lambda name=name: normalize_package(package(extra=[(name, b"x")]), ".docx"))
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = 0o120777 << 16
    c.rejects(lambda: normalize_package(package(extra=[(info, b"/etc/passwd")]), ".docx"))
    raw = bytearray(package())
    pos = raw.index(b"PK\x01\x02")
    raw[pos + 8] |= 1
    c.rejects(lambda: normalize_package(raw, ".docx"))


def par006(c):
    # PAR_006：每个资源阈值独立构造，其余维度保持合法。
    for count in (10000, 10001):
        raw = package(extra=[(f"f{i}.bin", b"x") for i in range(count - 1)])
        if count == 10000:
            c.check(normalize_package(raw, ".docx").text, "条目等于上限允许")
        else:
            c.rejects(lambda raw=raw: normalize_package(raw, ".docx"), codes={"ARTIFACT_UNSAFE"})
    for size in (64 * 1024**2, 64 * 1024**2 + 1):
        raw = package(extra=[("large.bin", b"a" * size)])
        if size == 64 * 1024**2:
            c.check(normalize_package(raw, ".docx").text, "单成员等于上限")
        else:
            c.rejects(lambda raw=raw: normalize_package(raw, ".docx"), codes={"ARTIFACT_UNSAFE"})
    for extra_byte in (0, 1):
        # 四个<64MiB成员加full.md，总展开正好256MiB或多1；不混淆单成员限制。
        text = "valid"
        total = 256 * 1024**2 - len(text)
        sizes = [64 * 1024**2] * 3
        sizes.append(total - sum(sizes) + extra_byte)
        raw = package(text, [(f"part{i}.bin", b"a" * size) for i, size in enumerate(sizes)])
        if not extra_byte:
            c.check(normalize_package(raw, ".docx").text, "总展开等于上限")
        else:
            c.rejects(lambda raw=raw: normalize_package(raw, ".docx"), codes={"ARTIFACT_UNSAFE"})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("full.md", "x" * 100000)
    c.rejects(lambda: normalize_package(stream.getvalue(), ".docx"), codes={"ARTIFACT_UNSAFE"})


def par007(c):
    # PAR_007：唯一full.md而非任挑某份。
    for raw in (package(None), package(extra=[("other/full.md", "conflict")]), b"broken-zip"):
        c.rejects(lambda raw=raw: normalize_package(raw, ".docx"))
    c.equal(normalize_package(package("valid body"), ".docx").text, "valid body", "唯一正文正常")


def par008(c):
    # PAR_008：图片或空白不算文本成功，不拉远端资产。
    for value in (
        " ",
        "![image](https://invalid.example/a.png)",
        "<img src='https://invalid.example/a.png'>",
    ):
        c.rejects(
            lambda value=value: normalize_package(package(value), ".pdf"),
            codes={"MINERU_EMPTY_OUTPUT"},
        )
    c.check(normalize_package(package("body text"), ".pdf").text, "真实文本对照")


def par009(c):
    # PAR_009：表格值可对照，危险标签不能成为有效外部资产。
    raw = package(
        (
            "<table><tr><th>项目</th><th>值</th></tr><tr><td>ALPHA</td><td>37</td"
            "></tr></table><script>do_not_execute()</script>"
        )
    )
    result = normalize_package(raw, ".xlsx")
    c.check("ALPHA" in result.text and "37" in result.text, "表格文本和值保留")
    c.check("<script" not in result.text, "脚本标签移除")


def par012(c):
    # PAR_012：唯一精确PDF映射+1，重复或非法位置不猜。
    for entries, expected in (
        ([{"type": "text", "text": "Body", "page_idx": 0}], 1),
        ([{"type": "text", "text": "Body", "page_idx": 1}], 2),
        ([{"type": "text", "text": "Body", "page_idx": -1}], None),
        ([{"type": "text", "text": "Body", "page_idx": 0}] * 2, None),
    ):
        artifact = normalize_package(
            package("Body", [("x_content_list.json", json.dumps(entries))]), ".pdf"
        )
        location = artifact.blocks[0].locations[0]
        c.equal(
            location.get("number") if location["kind"] == "page" else None,
            expected,
            "可靠/缺失原页映射",
        )


def par013(c):
    # PAR_013：办公无原位置只能normalized/block_only，不猜slide/sheet。
    for ext in (".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"):
        artifact = normalize_package(package(), ext)
        c.check(
            all(
                p["origin"] == "normalized" and p["quality"] == "block_only"
                for b in artifact.blocks
                for p in b.locations
            ),
            "缺原位置明确规范块：" + ext,
        )


def par014(c):
    # PAR_014：可选位置坏JSON不能伪造可靠源页，正文仍有效。
    for value in (b"bad-json", b"{}", b'[{"unknown":true}]'):
        artifact = normalize_package(package("Body", [("x_content_list.json", value)]), ".pdf")
        c.equal(artifact.text, "Body", "可选位置缺失不丢正文")
        c.check(
            all(p["origin"] != "source" for b in artifact.blocks for p in b.locations),
            "坏映射不猜源页",
        )
    c.rejects(lambda: normalize_package(b"invalid-entire-package", ".pdf"))


CASES = {
    **{f"MIN_{n:03}": globals()[f"min{n:03}"] for n in range(1, 23)},
    **{f"PAR_{n:03}": globals()[f"par{n:03}"] for n in list(range(1, 10)) + [12, 13, 14]},
}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
