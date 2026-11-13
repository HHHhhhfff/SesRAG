"""CAT_001～018：知识库/配置边界；CAT_016由real-business独立处理。"""

import copy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from helpers.case_runner import run_category
from helpers.common import SUITE, load

from backend.application.rag_profiles import KINDS, profile_reason
from backend.domain.rag import EmbeddingSpace
from backend.domain.rag_profiles import ParserConfig


def create(e, name, **kwargs):
    return e.client.post(
        "/api/v3/knowledge-bases",
        json={
            "name": name,
            "embedding_profile_id": "mock-embedding",
            "embedding_profile_version": 1,
            **kwargs,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )


def cat001(c):
    # CAT_001：名称合法/非法边界，创建和改名分别经过正式DTO/应用服务。
    e = c.environment()
    for i, name in enumerate(("", " ", "a", "b" * 80, "c" * 81, "  trimmed  ")):
        r = create(e, name)
        valid = 1 <= len(name.strip()) <= 80
        c.equal(r.status_code, 201 if valid else 422, "创建名称边界")
        if valid:
            identity = r.json()["knowledge_base_id"]
            c.equal(r.json()["name"], name.strip(), "去首尾空白读回")
            for value in (" ", "x" * 81, f"renamed-{i}"):
                r = e.client.patch("/api/v3/knowledge-bases/" + identity, json={"name": value})
                c.equal(r.status_code, 200 if value.startswith("renamed") else 422, "改名边界")


def cat002(c):
    # CAT_002：同owner已停用名称仍占用，独立PG连接并发首次建库。
    e = c.environment()
    a = create(e, "conflict").json()
    e.request("PATCH", "/api/v3/knowledge-bases/" + a["knowledge_base_id"], json={"enabled": False})
    c.equal(create(e, "conflict").status_code, 409, "停用也保留名称唯一性")
    b = create(e, "second").json()
    c.equal(
        e.client.patch(
            "/api/v3/knowledge-bases/" + b["knowledge_base_id"], json={"name": "conflict"}
        ).status_code,
        409,
        "改名冲突",
    )
    with ThreadPoolExecutor(2) as pool:
        statuses = sorted(pool.map(lambda _: create(e, "race").status_code, range(2)))
    c.equal(statuses, [201, 409], "并发只有一个首次成功")
    e.settings.owner_id = "rag-test-owner-b"
    c.equal(create(e, "conflict").status_code, 201, "服务端不同owner可同名")


def cat003(c):
    # CAT_003：首次/非默认及PG部分唯一约束。
    e = c.environment()
    c.equal(
        e.sql("SELECT count(*) AS n FROM knowledge_bases WHERE is_default")[0]["n"],
        1,
        "唯一初始化默认",
    )
    c.equal(create(e, "ordinary").json()["is_default"], False, "普通库不替换默认")
    c.rejects(lambda: e.sql("UPDATE knowledge_bases SET is_default=true WHERE name='ordinary'"))
    e.settings.owner_id = "rag-test-owner-b"
    c.equal(create(e, "first-b").json()["is_default"], True, "空owner首次库成为默认")
    c.equal(create(e, "next-b").json()["is_default"], False, "第二库不改默认")


def cat004(c):
    # CAT_004：身份来自服务端，不信任payload owner。
    e = c.environment()
    own = e.base
    e.settings.owner_id = "rag-test-owner-b"
    other = create(e, "B").json()["knowledge_base_id"]
    rows = e.request("GET", "/api/v3/knowledge-bases")["items"]
    c.equal([r["knowledge_base_id"] for r in rows], [other], "列表仅本owner")
    for identity in (own, str(uuid4())):
        for method in ("get", "patch"):
            r = getattr(e.client, method)(
                "/api/v3/knowledge-bases/" + identity,
                **({"json": {"name": "x"}} if method == "patch" else {}),
            )
            c.equal(r.status_code, 404, "越owner和不存在不可区分")


def cat005(c):
    # CAT_005：停用拒绝三种新操作，重启用可写。
    e = c.environment()
    doc = e.upload()
    e.request("PATCH", "/api/v3/knowledge-bases/" + e.base, json={"enabled": False})
    e.upload(expected=(409,), finish=False)
    e.request(
        "POST",
        "/api/v3/documents/" + doc["document_id"] + "/index-builds",
        expected=(409,),
        json={},
        headers={"Idempotency-Key": str(uuid4())},
    )
    e.request(
        "POST",
        "/api/v3/retrieval-executions",
        expected=(409,),
        json={"query": "a", "knowledge_base_id": e.base},
        headers={"Idempotency-Key": str(uuid4())},
    )
    e.request("PATCH", "/api/v3/knowledge-bases/" + e.base, json={"enabled": True})
    c.equal(e.upload()["availability"], "ready", "重新启用可正常发布")


def cat006(c):
    # CAT_006：停用选择不撤回已有冻结视图。
    e = c.environment()
    doc = e.upload()
    execution = e.diagnostic()
    bundle = e.request("GET", "/api/v3/evidence-bundles/" + execution["bundle_ids"][0])
    e.request("PATCH", "/api/v3/knowledge-bases/" + e.base, json={"enabled": False})
    c.equal(
        e.request("GET", "/api/v3/evidence-bundles/" + bundle["bundle_id"]),
        bundle,
        "历史证据仍原批次",
    )
    c.equal(bundle["index_batch_id"], doc["active_index_batch_id"], "对应原active")


def cat007(c):
    # CAT_007：接口未知身份字段和PG空间不可变双层约束。
    e = c.environment()
    for payload in ({"space_id": "forged"}, {"owner_id": "other"}, {"embedding_profile_id": "x"}):
        e.request("PATCH", "/api/v3/knowledge-bases/" + e.base, expected=(422,), json=payload)
    c.rejects(lambda: e.sql("UPDATE knowledge_bases SET embedding_space_id='forged'"))


def cat008(c):
    # CAT_008：空间身份包含模型/修订/归一化而不仅维度。
    first = EmbeddingSpace(model="a", revision="r1", dimension=384)
    values = [
        EmbeddingSpace(model="b", revision="r1", dimension=384),
        EmbeddingSpace(model="a", revision="r2", dimension=384),
        EmbeddingSpace(model="a", revision="r1", dimension=384, normalization="l2_float32_v1"),
        EmbeddingSpace(model="a", revision="r1", dimension=1024),
    ]
    c.equal(len({first.space_id, *(r.space_id for r in values)}), 5, "不同描述不合并空间")
    e = c.environment()
    for i, space in enumerate(values):
        e.import_profiles(
            [
                {
                    "kind": "embedding",
                    "profile_id": f"space-{i}",
                    "version": 1,
                    "config": {"space": space.model_dump()},
                }
            ]
        )
    c.equal(len(e.sql("SELECT DISTINCT space_id FROM embedding_profiles")), 5, "PG保存不同空间身份")


def cat009(c):
    # CAT_009：两次不同生成模型快照不能影响同库向量空间。
    e = c.environment()
    doc = e.upload()
    snapshots = []
    for model in ("mock-default", "mock-small"):
        run = e.run(model_profile_id=model, model_profile_version=1)
        snapshots.append(
            e.sql("SELECT snapshot_json FROM runs WHERE run_id=:id", {"id": run["run_id"]})[0][
                "snapshot_json"
            ]
        )
    c.equal(
        snapshots[0]["rag"]["config"]["embedding"],
        snapshots[1]["rag"]["config"]["embedding"],
        "生成切换不改Embedding配置",
    )
    c.equal(
        e.request("GET", "/api/v3/documents/" + doc["document_id"])["active_index_batch_id"],
        doc["active_index_batch_id"],
        "不隐式重建",
    )


def cat010(c):
    # CAT_010：四类Profile同版本重放和冲突，不能用启停重写配置。
    e = c.environment()
    for kind in KINDS:
        row = next(
            copy.deepcopy(r)
            for r in load(SUITE / "fixtures/profiles.local.json")
            if r["kind"] == kind
        )
        e.import_profiles([row])
        changed = copy.deepcopy(row)
        config = changed["config"]
        if kind == "embedding":
            config["space"]["revision"] = "new"
        elif kind == "parser":
            config["parse_timeout"] = 200
        elif kind == "rerank":
            config["max_query_bytes"] = 1024
        else:
            config["policy"] = {"top_k": 2}
        c.rejects(
            lambda changed=changed: e.import_profiles([changed]), codes={"PROFILE_VERSION_CONFLICT"}
        )
        changed["version"] += 1
        e.import_profiles([changed])
        c.check(True, "增版导入成功", kind)


def cat011(c):
    # CAT_011：普通选择停用不改变冻结版本。
    e = c.environment()
    doc = e.upload(finish=False)
    e.sql(
        "UPDATE embedding_profiles SET selection_status='disabled' "
        "WHERE profile_id='mock-embedding'"
    )
    e.finish("/api/v3/index-builds/" + doc["latest_build"]["index_batch_id"])
    c.equal(create(e, "disabled").status_code, 409, "新选择拒绝停用版本")
    c.equal(
        e.sql("SELECT embedding_snapshot FROM index_builds")[0]["embedding_snapshot"]["version"],
        1,
        "冻结仍原版",
    )


def cat012(c):
    # CAT_012：在query Embedding后屏障设置安全blocked，阻止后续rerank。
    e = c.environment()
    e.upload()
    for kind, table in (
        ("embedding", "embedding_profiles"),
        ("rerank", "rerank_profiles"),
        ("retrieval", "retrieval_profiles"),
    ):
        execution = e.diagnostic(finish=False, overrides={"rerank_enabled": True})
        e.sql(f"UPDATE {table} SET security_status='blocked'")
        row = e.finish(
            "/api/v3/retrieval-executions/" + execution["execution_id"], successful=False
        )
        c.equal(row["state"], "failed", "安全撤权停止外发：" + kind)
        c.equal(row["error_code"], "PROFILE_UNAVAILABLE", "安全撤权稳定错误")
        e.sql(f"UPDATE {table} SET security_status='allowed'")


def cat013(c):
    # CAT_013：公开Profile只保留安全选择字段。
    e = c.environment()
    data = e.request("GET", "/api/v3/rag/profiles")
    c.check(
        {"embedding", "rerank", "parser", "retrieval"} <= {r["kind"] for r in data["items"]},
        "四类安全配置可见",
    )
    serialized = str(data)
    c.check(
        all(s not in serialized for s in ("dummy-", "config_ref", "base_url", "MINERU_API_KEY")),
        "公开响应不含Key或私有配置",
    )


def cat014(c):
    # CAT_014：不以假evidence绕过unverified。
    from backend.infrastructure.providers.rag_registry import (
        embedding_from_profile,
        rerank_from_profile,
    )

    for row in load(SUITE / "fixtures/profiles.real.example.json"):
        if (
            row["kind"] in {"embedding", "rerank"}
            and row["config"].get("adapter_kind") == "bailian"
        ):
            row["config"]["counter_evidence"] = "untrusted-placeholder"
            c.equal(
                profile_reason(row["kind"], row["config"]),
                "INPUT_COUNTER_UNVERIFIED",
                "应用启用守卫",
            )
            factory = embedding_from_profile if row["kind"] == "embedding" else rerank_from_profile
            c.rejects(
                lambda factory=factory, row=row: factory(row), codes={"INPUT_COUNTER_UNVERIFIED"}
            )


def cat015(c):
    # CAT_015：Parser路由和逐格式依据必须匹配。
    for config in (
        {"parser_kind": "local", "formats": [".pdf"], "output_protocol": "local_structure_v1"},
        {
            "parser_kind": "mineru",
            "formats": [".txt"],
            "output_protocol": "mineru_cloud_v4_office_text_v1",
        },
        {
            "parser_kind": "mineru",
            "formats": [".pdf"],
            "verified_formats": [".pdf"],
            "output_protocol": "mineru_cloud_v4_office_text_v1",
        },
    ):
        c.rejects(
            lambda config=config: ParserConfig.model_validate(config), error_types=(ValueError,)
        )


def cat017(c):
    # CAT_017：生成计数配置完整及离线缓存安全，不发真实请求。
    from backend.application.model_profiles import validate_profile_config
    from backend.infrastructure.providers.context_counter import load_encoding_offline

    row = next(
        r
        for r in load(SUITE / "fixtures/models.local.json")
        if r["provider_kind"] == "openai_compatible"
    )
    for key in (
        "encoding_name",
        "message_overhead_tokens",
        "request_overhead_tokens",
        "calibration_version",
    ):
        value = copy.deepcopy(row)
        value["tokenizer_config"].pop(key)
        c.rejects(lambda value=value: validate_profile_config(value), error_types=(ValueError,))
    validate_profile_config(row)
    c.check(load_encoding_offline("cl100k_base").encode("中文🙂"), "显式encoding可离线加载")
    c.rejects(
        lambda: load_encoding_offline("nonexistent-encoding"), error_types=(ValueError, KeyError)
    )


def cat018(c):
    # CAT_018：库及文档分页的边界/游标/去重。
    e = c.environment()
    for i in range(3):
        c.equal(create(e, f"page-{i}").status_code, 201, "分页前置独立创建")
        e.upload(filename=f"p{i}.txt")
    for path in ("/api/v3/knowledge-bases", "/api/v3/documents"):
        base_params = {"knowledge_base_id": e.base} if "documents" in path else {}
        ids, cursor = [], None
        while True:
            page = e.request(
                "GET",
                path,
                params={**base_params, "limit": 1, **({"cursor": cursor} if cursor else {})},
            )
            ids += [r.get("document_id", r.get("knowledge_base_id")) for r in page["items"]]
            cursor = page["next_cursor"]
            if not cursor:
                break
        c.equal(len(ids), len(set(ids)), "分页无重复")
        c.equal(len(ids), 3 if "documents" in path else 4, "分页无遗漏")
        for limit in (0, 201):
            e.request("GET", path, expected=(422,), params={**base_params, "limit": limit})
        e.request("GET", path, expected=(422,), params={**base_params, "cursor": "%%%"})


CASES = {f"CAT_{n:03}": globals()[f"cat{n:03}"] for n in list(range(1, 16)) + [17, 18]}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
