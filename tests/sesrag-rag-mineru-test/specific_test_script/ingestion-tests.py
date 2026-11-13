"""INP_001～021：原源、固定路由、授权、幂等与产物复用。"""

import hashlib
import io
import zipfile
from pathlib import Path
from uuid import uuid4

from helpers.case_runner import run_category

from backend.application.index_builds import validate_tags
from backend.domain.rag import CONSENT_VERSION, ParseRequest
from backend.infrastructure.rag.office_validation import MIMES, validate_source


def source(extension):
    paths = sorted(Path("/inputs").glob("*" + extension))
    if not paths:
        raise ValueError("FIXED_SOURCE_MISSING_" + extension)
    return paths[0].read_bytes()


def office_parse(**extra):
    return {"cloud_consent": True, "consent_version": CONSENT_VERSION, **extra}


def rebuild(e, doc, payload=None, key=None, expected=(202,)):
    return e.request(
        "POST",
        f"/api/v3/documents/{doc['document_id']}/index-builds",
        expected=expected,
        json=payload or {},
        headers={"Idempotency-Key": key or str(uuid4())},
    )


def inp001(c):
    # INP_001：每个真实容器格式正例，白名单外负例。
    for ext in MIMES:
        name, resolved = validate_source("Source" + ext.upper(), None, source(ext))
        c.equal(resolved, ext, "大小写后缀归一化：" + ext)
        c.equal(Path(name).suffix, ext.upper(), "保留安全文件名")
    for ext in (".html", ".png", ".exe", ".docm"):
        c.rejects(
            lambda ext=ext: validate_source("x" + ext, None, b"text"),
            codes={"UNSUPPORTED_DOCUMENT_TYPE"},
        )


def inp002(c):
    # INP_002：目录前缀只留basename；存储键仍服务端生成。
    for name in ("../folder/a.txt", "C:\\folder\\a.txt"):
        c.equal(validate_source(name, None, b"text")[0], "a.txt", "安全basename")
    for name in ("", "a:bad.txt", "a\x00.txt", "a\x7f.txt", "a" * 252 + ".txt"):
        c.rejects(
            lambda name=name: validate_source(name, None, b"text"),
            codes={"INVALID_DOCUMENT_FILENAME"},
        )
    e = c.environment()
    doc = e.upload(filename="../folder/a.txt")
    row = e.sql(
        "SELECT storage_key FROM documents WHERE document_id=:id", {"id": doc["document_id"]}
    )[0]
    c.equal(
        row["storage_key"],
        "documents/" + doc["document_id"] + "/source.txt",
        "客户端路径不决定存储键",
    )


def inp003(c):
    # INP_003：10MiB按1024平方，边界前置拒绝无事实。
    validate_source("x.txt", None, b"A" * (10 * 1024**2))
    c.check(True, "恰好10MiB通过源预检")
    c.rejects(
        lambda: validate_source("x.txt", None, b"A" * (10 * 1024**2 + 1)),
        codes={"DOCUMENT_TOO_LARGE"},
    )
    c.rejects(lambda: validate_source("x.txt", None, b""), codes={"EMPTY_DOCUMENT"})
    e = c.environment()
    e.upload(raw=b"A" * (10 * 1024**2 + 1), expected=(413,), finish=False)
    c.equal(e.sql("SELECT count(*) n FROM documents")[0]["n"], 0, "超限无Document或远端Job")


def inp004(c):
    # INP_004：内容/扩展名/MIME共同判断。
    for ext, mimes in MIMES.items():
        raw = source(ext)
        for mime in (None, "application/octet-stream", *mimes):
            c.equal(validate_source("x" + ext, mime, raw)[1], ext, "合法MIME或未声明")
        wrong = "application/pdf" if ext != ".pdf" else "text/plain"
        c.rejects(
            lambda ext=ext, raw=raw, wrong=wrong: validate_source("x" + ext, wrong, raw),
            codes={"DOCUMENT_MIME_MISMATCH"},
        )
    for ext in (".pdf", ".docx", ".xls"):
        c.rejects(
            lambda ext=ext: validate_source("x" + ext, None, b"plain text"), codes={"SOURCE_UNSAFE"}
        )


def inp005(c):
    # INP_005：UTF-8/BOM合法，非法编码/NUL/全空白拒绝。
    for raw in ("中文🙂".encode(), b"\xef\xbb\xbftext"):
        c.equal(validate_source("x.txt", None, raw)[1], ".txt", "有效文本")
    for raw in (b"\xff", b"a\x00b", b" \r\n\t"):
        c.rejects(lambda raw=raw: validate_source("x.md", None, raw), codes={"SOURCE_UNSAFE"})


def mutated_zip(raw, *, remove=(), additions=()):
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as original, zipfile.ZipFile(out, "w") as result:
        for row in original.infolist():
            if row.filename not in remove:
                result.writestr(row, original.read(row))
        for name, value in additions:
            result.writestr(name, value)
    return out.getvalue()


def inp006(c):
    # INP_006：OOXML主部件、路径、宏/对象/外部关系；合法hyperlink不执行。
    for ext, main in (
        (".docx", "word/document.xml"),
        (".xlsx", "xl/workbook.xml"),
        (".pptx", "ppt/presentation.xml"),
    ):
        raw = source(ext)
        variants = [
            mutated_zip(raw, remove=[main]),
            mutated_zip(raw, remove=["[Content_Types].xml"]),
        ]
        for member in (
            "../escape",
            "/absolute",
            "word/vbaProject.bin",
            "word/embeddings/object.bin",
            main,
        ):
            variants.append(mutated_zip(raw, additions=[(member, b"synthetic")]))
        external = (
            '<Relationships><Relationship TargetMode="External" Type="image" T'
            'arget="https://invalid.example/a"/></Relationships>'
        )
        variants.append(mutated_zip(raw, additions=[("fixture.rels", external)]))
        for value in variants:
            c.rejects(
                lambda ext=ext, value=value: validate_source("x" + ext, None, value),
                codes={"SOURCE_UNSAFE"},
            )
        hyperlink = external.replace('Type="image"', 'Type="relationship/hyperlink"')
        c.equal(
            validate_source(
                "x" + ext, None, mutated_zip(raw, additions=[("fixture.rels", hyperlink)])
            )[1],
            ext,
            "普通超链接可保留但不访问",
        )


def inp007(c):
    # INP_007：真实OLE正例，错误主流/坏头/改后缀负例。
    for ext in (".doc", ".xls", ".ppt"):
        raw = source(ext)
        c.equal(validate_source("x" + ext, None, raw)[1], ext, "真实旧Office容器")
        for value in (b"broken" + raw[6:], source(".docx")):
            c.rejects(
                lambda ext=ext, value=value: validate_source("x" + ext, None, value),
                codes={"SOURCE_UNSAFE"},
            )
    c.rejects(lambda: validate_source("wrong.xls", None, source(".doc")), codes={"SOURCE_UNSAFE"})


def inp008(c):
    # INP_008：本地PDF浅校验不能冒充正文解析，内部坏PDF由远端明确失败。
    for raw in (b"bad", b"%PDF-1.7\nno-end"):
        c.rejects(lambda raw=raw: validate_source("x.pdf", None, raw), codes={"SOURCE_UNSAFE"})
    raw = b"%PDF-1.7\ncorrupt-internal\n%%EOF"
    validate_source("x.pdf", None, raw)
    e = c.environment()
    doc = e.upload(raw=raw, filename="broken.pdf", finish=False)
    job = doc["latest_build"]["parse"]["parse_job_id"]
    e.plan(job, "mineru_poll", [{"state": "failed"}])
    row = e.finish(
        "/api/v3/index-builds/" + doc["latest_build"]["index_batch_id"], successful=False
    )
    c.equal(row["state"], "failed", "坏PDF不回退成功")


def inp009(c):
    # INP_009：无MinerU配置下两种文本完整发布。
    e = c.environment(mineru_enabled=False, mineru_api_key=None)
    for ext in (".txt", ".md"):
        doc = e.upload(raw=source(ext), filename="local" + ext)
        c.equal(doc["latest_build"]["parse"]["parser_kind"], "local", "固定本地解析")
        c.equal(
            e.observations(doc["latest_build"]["parse"]["parse_job_id"])["mineru_submit"]["count"],
            0,
            "无云申请",
        )


def inp010(c):
    # INP_010：七办公每次上传和重建均逐次授权。
    e = c.environment()
    for ext in (".doc", ".docx", ".pdf", ".xls", ".xlsx", ".ppt", ".pptx"):
        for parse in (
            {},
            {"cloud_consent": False},
            {"cloud_consent": True, "consent_version": "old"},
        ):
            e.upload(
                raw=source(ext), filename="x" + ext, parse=parse, expected=(422,), finish=False
            )
        doc = e.upload(raw=source(ext), filename="x" + ext)
        rebuild(e, doc, expected=(422,))
        build = rebuild(e, doc, {"parse": office_parse()})
        e.finish("/api/v3/index-builds/" + build["index_batch_id"])


def inp011(c):
    # INP_011：文本拒绝云授权和路由覆盖字段。
    for ext in (".txt", ".md"):
        c.rejects(
            lambda ext=ext: ParseRequest(**office_parse()).resolve(ext),
            codes={"INVALID_PARSE_SELECTION"},
        )
    for key in ("mode", "fallback", "converter", "url"):
        c.rejects(
            lambda key=key: ParseRequest.model_validate({key: "local"}), error_types=(ValueError,)
        )
    e = c.environment()
    e.upload(
        parse={"parser_profile_id": "mineru-office", "parser_profile_version": 2},
        expected=(422,),
        finish=False,
    )


def inp012(c):
    # INP_012：已知缺配置前置拒绝，且本地仍能完成。
    from helpers.common import SUITE, load

    from backend.application.rag_profiles import profile_reason
    from backend.config import Settings

    config = next(
        r["config"]
        for r in load(SUITE / "fixtures/profiles.local.json")
        if r["profile_id"] == "mineru-office"
    )
    for changes in (
        {"mineru_enabled": False},
        {"mineru_api_key": None},
        {"mineru_state_encryption_key": None},
        {"mineru_storage_host_allowlist": ""},
    ):
        settings = Settings(_env_file=None, **changes)
        c.check(
            profile_reason("parser", config, settings, ".pdf") is not None,
            "已知缺配置不可用",
            list(changes),
        )
    e = c.environment(mineru_enabled=False)
    e.upload(raw=source(".docx"), filename="x.docx", expected=(409,), finish=False)
    c.equal(e.sql("SELECT count(*) n FROM parse_jobs")[0]["n"], 0, "拒绝不留Job")
    e.upload()


def inp013(c):
    # INP_013：PUT原件hash一致；源变更不能继续解析。
    e = c.environment()
    raw = source(".docx")
    doc = e.upload(raw=raw, filename="x.docx")
    c.equal(doc["content_hash"], hashlib.sha256(raw).hexdigest(), "登记原件hash")
    job = doc["latest_build"]["parse"]["parse_job_id"]
    payload = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    from helpers.common import digest

    c.equal(
        e.observations(job)["mineru_put"]["last"]["request_hash"],
        digest(payload),
        "PUT确为原件字节，无转换",
    )
    second = e.upload(raw=raw, filename="y.docx", finish=False)
    storage = e.sql(
        "SELECT storage_key FROM documents WHERE document_id=:id", {"id": second["document_id"]}
    )[0]["storage_key"]
    (e.settings.upload_path / storage).write_bytes(b"tampered")
    row = e.finish(
        "/api/v3/index-builds/" + second["latest_build"]["index_batch_id"], successful=False
    )
    c.equal(row["state"], "failed", "篡改源不得解析成功")


def inp014(c):
    # INP_014：标签合法/类型/长度，补丁不能覆盖系统身份。
    for value in ([], ["a"], ["a", " a "], [str(i) for i in range(20)]):
        c.equal(
            validate_tags(value), list(dict.fromkeys(t.strip() for t in value)), "标签去空白去重"
        )
    for value in (
        [""],
        [" "],
        ["x" * 41],
        [1],
        [["x"]],
        {"batch": "forged"},
        [str(i) for i in range(21)],
    ):
        c.rejects(lambda value=value: validate_tags(value), codes={"INVALID_RAG_PARAMETER"})
    e = c.environment()
    doc = e.upload()
    e.request(
        "PATCH",
        "/api/v3/documents/" + doc["document_id"],
        expected=(422,),
        json={"tags": [], "space_id": "forged"},
    )


def inp015(c):
    # INP_015：源字节修改必须新Document，改标签不改源。
    e = c.environment()
    a, b = e.upload(raw=b"one"), e.upload(raw=b"two")
    c.check(
        a["document_id"] != b["document_id"] and a["content_hash"] != b["content_hash"],
        "不同源独立身份",
    )
    changed = e.request("PATCH", "/api/v3/documents/" + a["document_id"], json={"tags": ["new"]})
    c.equal(changed["content_hash"], a["content_hash"], "标签不覆盖源")
    e.request(
        "PUT", "/api/v3/documents/" + a["document_id"], expected=(405,), json={"text": "override"}
    )


def inp016(c):
    # INP_016：同源不同操作不跨owner去重。
    e = c.environment()
    a, b = e.upload(), e.upload()
    c.check(a["document_id"] != b["document_id"], "同源新操作可独立上传")
    c.equal(a["content_hash"], b["content_hash"], "内容相同不等于身份相同")
    e.settings.owner_id = "rag-test-owner-b"
    e.request("GET", "/api/v3/documents/" + a["document_id"], expected=(404,))


def inp017(c):
    # INP_017：建库/上传/重建/诊断各scope的同key重放。
    e = c.environment()
    key = str(uuid4())
    payload = {
        "name": "idempotent",
        "embedding_profile_id": "mock-embedding",
        "embedding_profile_version": 1,
    }
    first = e.request(
        "POST",
        "/api/v3/knowledge-bases",
        expected=(201,),
        json=payload,
        headers={"Idempotency-Key": key},
    )
    c.equal(
        e.request(
            "POST", "/api/v3/knowledge-bases", json=payload, headers={"Idempotency-Key": key}
        )["knowledge_base_id"],
        first["knowledge_base_id"],
        "建库同键重放",
    )
    doc = e.upload(key=key)
    c.equal(
        e.upload(key=key, expected=(200,))["document_id"], doc["document_id"], "上传scope独立且重放"
    )
    build = rebuild(e, doc, key=key)
    c.equal(
        rebuild(e, doc, key=key, expected=(200,))["index_batch_id"],
        build["index_batch_id"],
        "重建重放",
    )
    diagnostic = {"query": "ALPHA", "knowledge_base_id": e.base}
    first = e.request(
        "POST",
        "/api/v3/retrieval-executions",
        expected=(202,),
        json=diagnostic,
        headers={"Idempotency-Key": key},
    )
    c.equal(
        e.request(
            "POST",
            "/api/v3/retrieval-executions",
            json=diagnostic,
            headers={"Idempotency-Key": key},
        )["execution_id"],
        first["execution_id"],
        "诊断重放",
    )


def inp018(c):
    # INP_018：同scope改内容冲突，键只按真实1～200字符串规则。
    e = c.environment()
    key = str(uuid4())
    e.upload(key=key)
    e.upload(raw=b"changed", key=key, expected=(409,), finish=False)
    for key in ("", "x" * 201):
        e.upload(key=key, expected=(422,), finish=False)
    c.equal(
        e.upload(key="spaces and unicode-中文".encode())["availability"],
        "ready",
        "传输层显式编码非ASCII头字节，不虚构UUID限制",
    )


def inp019(c):
    # INP_019：活动同配置复用，异配置忙，真PG约束核对。
    e = c.environment()
    doc = e.upload()
    a, b = rebuild(e, doc), rebuild(e, doc)
    c.equal(a["index_batch_id"], b["index_batch_id"], "同配置活动Build复用")
    rebuild(e, doc, {"chunker": {"size": 200, "overlap": 20}}, expected=(409,))
    c.equal(
        e.sql("SELECT count(*) n FROM index_builds WHERE state IN ('queued','building','waiting')")[
            0
        ]["n"],
        1,
        "只有一个活动候选",
    )


def inp020(c):
    # INP_020：同文档成功解析复用；新文档不能按hash冒认。
    e = c.environment()
    a = e.upload(raw=source(".docx"), filename="x.docx")
    old = a["latest_build"]["parse"]
    rebuild(e, a, expected=(422,))
    new = rebuild(e, a, {"parse": office_parse()})
    c.equal(new["parse"]["artifact_id"], old["artifact_id"], "源/解析配置相同可复用产物")
    b = e.upload(raw=source(".docx"), filename="x.docx")
    c.check(
        b["latest_build"]["parse"]["artifact_id"] != old["artifact_id"], "跨Document不复用Artifact"
    )


def inp021(c):
    # INP_021：未知提交沿旧key重放，新操作逐次授权并确认潜在成本。
    e = c.environment()
    doc = e.upload(raw=source(".docx"), filename="x.docx", finish=False)
    e.plan(doc["latest_build"]["parse"]["parse_job_id"], "mineru_submit", [{"fault": "connection"}])
    failed = e.finish(
        "/api/v3/index-builds/" + doc["latest_build"]["index_batch_id"], successful=False
    )
    c.equal(failed["parse"]["remote_outcome"], "unknown_may_continue", "未知提交持久风险")
    rebuild(e, doc, {"parse": office_parse()}, expected=(409,))
    new = rebuild(e, doc, {"parse": office_parse(acknowledge_duplicate_cost=True)})
    c.check(new["index_batch_id"] != failed["index_batch_id"], "明确确认后可新建操作")
    c.equal(
        e.request("GET", "/api/v3/index-builds/" + failed["index_batch_id"])["state"],
        "failed",
        "旧未知终态不复活",
    )


CASES = {f"INP_{n:03}": globals()[f"inp{n:03}"] for n in range(1, 22)}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
