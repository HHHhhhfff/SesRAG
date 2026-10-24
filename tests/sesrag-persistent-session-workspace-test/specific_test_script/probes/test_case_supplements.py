"""用例精确子场景补充；调用正式应用/Worker/Port，不直接预造成功事实。"""

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta, timezone

import pytest
from sqlalchemy import select

from backend.api.schemas.v2.threads import BranchCreate, MessageCreate
from backend.application.branches import create_branch
from backend.application.context import ContextInput, ModelMessage, check_mandatory_budget
from backend.application.errors import PermanentTaskError, TransientTaskError
from backend.application.session_runs import context_detail, create_session_message
from backend.application.threads import create_thread
from backend.db.models import (
    BranchModel,
    ConversationSummaryModel,
    MessageModel,
    ModelProfileModel,
    TaskModel,
)
from backend.infrastructure.providers.context_counter import (
    MockTokenCounter,
    token_counter_from_profile,
)
from backend.infrastructure.queue import postgres_queue as queue
from backend.infrastructure.session.context import SQLContextRepository
from backend.infrastructure.session.model_profiles import SQLModelProfileRepository
from tests.api.test_v2_run_api import seed as seed_api
from tests.api.test_v2_session_api import client_for, mutate
from tests.integration.conftest import document_db as document_db
from tests.integration.test_v2_run_execution import (
    EmptyStore,
    facts,
    runtime,
    submit,
)
from tests.integration.test_v2_run_execution import (
    workspace as workspace,
)
from tests.unit.test_model_profiles import profile, real_profile


class CaptureProvider:
    def __init__(self):
        self.requests = []

    async def stream_request(self, request):
        self.requests.append(request)
        yield "ASSISTANT_OLD"


# CTX_005/006：四组独立真实Worker计划，复算实收请求并验证retry真正复用派生摘要。
@pytest.mark.parametrize("variant", ["none", "trim", "summary", "retry"])
async def test_CTX_005_006_plan_variants(workspace, monkeypatch, variant):
    from backend.application.errors import ApplicationError
    from backend.db.models import ContextPlanModel

    settings, factory, tid, bid = workspace
    capture = CaptureProvider()
    worker = runtime(workspace, capture)
    rounds = 0 if variant == "none" else 1 if variant == "trim" else 2
    for index in range(rounds):
        await submit(workspace, "多字节 Unicode。 " + "old " * 1200, index * 2, f"old-{index}")
        assert await worker.run_once()
    async with factory() as session:
        old = await session.get(ModelProfileModel, ("mock-default", 1))
        config = {field: deepcopy(getattr(old, field)) for field in profile()}
        config.update(version=2, context_window_tokens=2048, max_output_tokens=256)
        await SQLModelProfileRepository(session).import_profiles([config])
        branch = await session.get(BranchModel, bid)
        created, _ = await create_session_message(
            session,
            settings,
            tid,
            MessageCreate(
                branch_id=bid,
                content="q " * 1648 if variant == "trim" else "followup",
                expected_version=branch.version,
                model_profile_id="mock-default",
                model_profile_version=2,
            ),
            f"variant-{variant}",
        )
        assert await context_detail(session, settings, created["run_id"]) == {
            "plan": None,
            "reason": "not_planned",
        }

    class Observed:
        def __init__(self):
            self.requests = []

        async def stream_request(self, request):
            self.requests.append(request)
            yield "answer"
            if variant == "retry" and len(self.requests) == 1:
                raise TransientTaskError("SYNTHETIC_RETRY", "controlled first attempt")

    provider = Observed()
    worker = runtime(workspace, provider)
    before = None
    for attempt in range(2 if variant == "retry" else 1):
        assert await worker.run_once()
        _, task, _ = await facts(workspace, created["run_id"])
        async with factory() as session:
            current = (await context_detail(session, settings, created["run_id"]))["plan"]
            by_generation = await context_detail(
                session, settings, created["run_id"], task.generation
            )
            assert current == by_generation["plan"]
            counter = token_counter_from_profile(config)
            assert current["estimated_input_tokens"] == counter.count_messages(
                provider.requests[-1].messages
            )
            assert current["counter_version"] == counter.version
            assert current["estimated_input_tokens"] + 256 + 128 <= 2048
            assert provider.requests[-1].max_output_tokens == 256
            if variant == "none":
                assert not current["omitted_messages"] and not current["summaries"]
            elif variant == "trim":
                assert current["omitted_messages"] and not current["summaries"]
            else:
                assert current["summaries"]
            if before:
                # 失败attempt未改历史，第二计划应复用相同来源摘要；旧计划原样保留。
                assert current["summaries"] == before["summaries"]
                assert (await context_detail(session, settings, created["run_id"], 1))[
                    "plan"
                ] == before
            before = deepcopy(current)
            with pytest.raises(ApplicationError, match="计划不存在"):
                await context_detail(session, settings, created["run_id"], 999)
            plans = (
                await session.scalars(
                    select(ContextPlanModel).where(ContextPlanModel.run_id == created["run_id"])
                )
            ).all()
            assert len(plans) == attempt + 1
        if task.state == "retry_waiting":
            future = task.available_at.replace(tzinfo=timezone.utc) + timedelta(milliseconds=1)
            monkeypatch.setattr(queue, "utc_now", lambda future=future: future)
    print(f"CTX_005/006：{variant}真实计划与实收计数/预算/代数一致")


# RUN_023：原始协议经过正式适配器及完整Worker重试，不只检查异常类。
@pytest.mark.parametrize(
    "mode", ["empty", "whitespace", "json", "nonstring", "disconnect", "no_done", "timeout"]
)
async def test_RUN_023_protocol_worker_terminal(workspace, monkeypatch, mode):
    from backend.infrastructure.providers.openai_compatible import OpenAICompatibleProvider

    provider = OpenAICompatibleProvider("http://controlled.invalid/v1", "fake", "model", "embed")

    async def raw(_endpoint, _payload):
        import json

        content = 42 if mode == "nonstring" else "  " if mode == "whitespace" else "partial"
        if mode == "json":
            yield b"data: {bad-json}\n\n"
            return
        if mode != "empty":
            yield (
                "data: " + json.dumps({"choices": [{"delta": {"content": content}}]}) + "\n\n"
            ).encode()
        if mode in {"disconnect", "timeout"}:
            raise TransientTaskError(
                "PROVIDER_TIMEOUT" if mode == "timeout" else "PROVIDER_TRANSPORT_ERROR",
                "controlled",
            )
        if mode != "no_done":
            yield b"data: [DONE]\n\n"

    monkeypatch.setattr(provider, "_bytes", raw)
    created = await submit(workspace)
    worker = runtime(workspace, provider)
    attempts = 3 if mode in {"disconnect", "timeout"} else 1
    for _ in range(attempts):
        assert await worker.run_once()
        result, task, journal = await facts(workspace, created["run_id"])
        if task.state == "retry_waiting":
            future = task.available_at.replace(tzinfo=timezone.utc) + timedelta(milliseconds=1)
            monkeypatch.setattr(queue, "utc_now", lambda future=future: future)
    assert result.status == task.state == "failed" and task.attempt == attempts
    assert result.assistant_message_id is None
    assert sum(event.type == "run.failed" for event in journal) == 1
    expected = (
        "PROVIDER_EMPTY_CONTENT"
        if mode in {"empty", "whitespace"}
        else "PROVIDER_TIMEOUT"
        if mode == "timeout"
        else "PROVIDER_TRANSPORT_ERROR"
        if mode == "disconnect"
        else "PROVIDER_INVALID_RESPONSE"
    )
    assert result.last_error_code == expected
    async with workspace[1]() as session:
        assert not (
            await session.scalars(
                select(MessageModel).where(
                    MessageModel.run_id == created["run_id"], MessageModel.role == "assistant"
                )
            )
        ).all()


# CTX_002/007：摘要由真实Worker产生，再验证仓储归属与后续请求隔离。
async def test_CTX_002_007_summary_scope_and_reuse(workspace):
    settings, factory, tid, bid = workspace
    capture = CaptureProvider()
    worker = runtime(workspace, capture)
    first = await submit(workspace, "A_ONLY source " * 1200)
    assert await worker.run_once()
    async with factory() as session:
        old = await session.get(ModelProfileModel, ("mock-default", 1))
        config = {field: deepcopy(getattr(old, field)) for field in profile()}
        config.update(version=2, context_window_tokens=2048, max_output_tokens=256)
        await SQLModelProfileRepository(session).import_profiles([config])
        current, _ = await create_session_message(
            session,
            settings,
            tid,
            MessageCreate(
                branch_id=bid,
                content="followup",
                expected_version=2,
                model_profile_id="mock-default",
                model_profile_version=2,
            ),
            "small",
        )
    assert await worker.run_once()
    async with factory() as session:
        plan = await context_detail(session, settings, current["run_id"])
        assert plan["plan"]["summaries"]
        meta = plan["plan"]["summaries"][0]
        summary = await session.get(ConversationSummaryModel, meta["summary_id"])
        repository = SQLContextRepository(session)
        assert (
            await repository.find_reusable_summary(
                tid, bid, summary.source_hash, summary.summary_policy_version
            )
        ).summary_id == summary.summary_id
        child, _ = await create_branch(
            session,
            settings,
            tid,
            BranchCreate(parent_branch_id=bid, fork_message_id=first["message_id"]),
            "child",
        )
        other = await create_thread(session, settings, "B_ONLY", conversation_version=2)
        ob = await session.scalar(
            select(BranchModel).where(BranchModel.thread_id == other.thread_id)
        )
        assert (
            await repository.find_reusable_summary(
                tid, child.branch_id, summary.source_hash, summary.summary_policy_version
            )
            is None
        )
        assert (
            await repository.find_reusable_summary(
                other.thread_id, ob.branch_id, summary.source_hash, summary.summary_policy_version
            )
            is None
        )
        other_result, _ = await create_session_message(
            session,
            settings,
            other.thread_id,
            MessageCreate(branch_id=ob.branch_id, content="B_ONLY input", expected_version=0),
            "other",
        )
    assert await worker.run_once()
    assert "A_ONLY" not in "|".join(message.content for message in capture.requests[-1].messages)
    run, task, _ = await facts(workspace, other_result["run_id"])
    assert run.status == task.state == "succeeded"
    async with factory() as session:
        assert (
            await session.get(ConversationSummaryModel, meta["summary_id"])
        ).source_hash == meta["source_hash"]
        sibling, _ = await create_branch(
            session,
            settings,
            tid,
            BranchCreate(parent_branch_id=bid, fork_message_id=first["message_id"]),
            "sibling",
        )
    nested_anchor = None
    for label, branch_id in [
        ("child", child.branch_id),
        ("sibling", sibling.branch_id),
        ("nested", None),
    ]:
        async with factory() as session:
            if label == "nested":
                nested, _ = await create_branch(
                    session,
                    settings,
                    tid,
                    BranchCreate(parent_branch_id=child.branch_id, fork_message_id=nested_anchor),
                    "nested",
                )
                branch_id = nested.branch_id
            branch = await session.get(BranchModel, branch_id)
            result, _ = await create_session_message(
                session,
                settings,
                tid,
                MessageCreate(
                    branch_id=branch_id,
                    content=f"{label} local input",
                    expected_version=branch.version,
                    model_profile_id="mock-default",
                    model_profile_version=2,
                ),
                f"input-{label}",
            )
        assert await worker.run_once()
        if label == "child":
            nested_anchor = result["message_id"]
        async with factory() as session:
            projected = (await context_detail(session, settings, result["run_id"]))["plan"]
            assert projected["summaries"], f"{label}必须真实触发派生摘要"
            for derived in projected["summaries"]:
                assert derived["summary_id"] != meta["summary_id"]
                record = await session.get(ConversationSummaryModel, derived["summary_id"])
                assert record.thread_id == tid and record.branch_id == branch_id
            original = await session.get(ConversationSummaryModel, meta["summary_id"])
            assert original.source_hash == meta["source_hash"] and original.branch_id == bid
        assert "followup" not in "|".join(
            message.content for message in capture.requests[-1].messages
        )


# CTX_003：Mock和真实离线tiktoken均精确等于/超过一token预算。
@pytest.mark.parametrize("kind", ["mock", "tiktoken"])
def test_CTX_003_exact_mandatory_boundary(kind):
    counter = MockTokenCounter() if kind == "mock" else token_counter_from_profile(real_profile())
    messages = (ModelMessage("system", "固定系统规则"), ModelMessage("user", "当前输入 Unicode。"))
    used = counter.count_messages(messages)
    request = ContextInput(
        "t", "b", "m", messages[1].content, messages[0].content, used + 256 + 128, 256, 128, (), ()
    )
    assert check_mandatory_budget(request, counter).status == "ready"
    assert (
        check_mandatory_budget(
            replace(request, context_window_tokens=request.context_window_tokens - 1), counter
        ).failure_reason
        == "CONTEXT_TOO_LARGE"
    )


# CTX_012：检索与Embedding错误由真实Worker结算，不能作为空结果成功。
@pytest.mark.parametrize("failure", ["none", "embedding", "vector"])
async def test_CTX_012_empty_vs_infrastructure(workspace, failure):
    capture = CaptureProvider()

    class FailingStore(EmptyStore):
        async def search(self, *args):
            raise PermanentTaskError("VECTOR_QUERY_FAILED", "安全检索失败")

    class Embedding:
        async def embed(self, value):
            raise PermanentTaskError("EMBEDDING_INVALID", "安全Embedding失败")

    created = await submit(workspace)
    worker = runtime(workspace, capture, FailingStore if failure == "vector" else EmptyStore)
    if failure == "embedding":
        worker.embedding_provider = Embedding()
    assert await worker.run_once()
    run, task, journal = await facts(workspace, created["run_id"])
    if failure == "none":
        assert run.status == task.state == "succeeded" and capture.requests
    else:
        assert run.status == task.state == "failed" and not capture.requests
        assert run.assistant_message_id is None
        assert journal[-1].type == "run.failed"


# MOD_004：同ID/version所有生成配置字段冲突均拒绝，不只检查model_name。
@pytest.mark.parametrize(
    "field,value",
    [
        ("model_name", "changed"),
        ("base_url", "http://provider:8080/v1"),
        ("generation_params", {"temperature": 0.7}),
        ("context_window_tokens", 4096),
        ("max_output_tokens", 512),
        ("tokenizer_version", "changed"),
    ],
)
async def test_MOD_004_immutable_fields(workspace, field, value):
    _, factory, *_ = workspace
    async with factory() as session:
        row = await session.get(ModelProfileModel, ("mock-default", 1))
        before = {name: deepcopy(getattr(row, name)) for name in profile()}
        with pytest.raises(ValueError):
            await SQLModelProfileRepository(session).import_profiles([{**before, field: value}])
        await session.rollback()
        restored = await session.get(ModelProfileModel, ("mock-default", 1))
        assert {name: getattr(restored, name) for name in before} == before


# MOD_005：真实HTTP Profile在创建后撤销Key，旧Run不得回退Mock。
async def test_MOD_005_revoked_runtime_key(workspace, monkeypatch):
    settings, factory, tid, bid = workspace
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-before-revoke")
    async with factory() as session:
        config = real_profile(profile_id="http", is_default=True)
        await SQLModelProfileRepository(session).import_profiles([config])
        created, _ = await create_session_message(
            session,
            settings,
            tid,
            MessageCreate(
                branch_id=bid,
                content="credential input",
                expected_version=0,
                model_profile_id="http",
                model_profile_version=1,
            ),
            "credential",
        )
    monkeypatch.delenv("MODEL_API_KEY")
    assert await runtime(workspace).run_once()
    run, task, _ = await facts(workspace, created["run_id"])
    assert run.status == task.state == "failed"
    assert run.last_error_code == "MODEL_CREDENTIAL_UNAVAILABLE"
    assert run.assistant_message_id is None


# RUN_002：首delta已提交时，最终Message仍不存在，终态未宣布。
async def test_RUN_002_draft_is_not_message(workspace):
    created = await submit(workspace)
    entered, release = asyncio.Event(), asyncio.Event()

    class Provider:
        async def stream_request(self, request):
            yield "draft"
            entered.set()
            await release.wait()
            yield "tail"

    operation = asyncio.create_task(runtime(workspace, Provider()).run_once())
    try:
        await asyncio.wait_for(entered.wait(), 3)
        async with asyncio.timeout(3):
            while True:
                run, _, journal = await facts(workspace, created["run_id"])
                if any(event.type == "answer.delta" for event in journal):
                    break
                await asyncio.sleep(0.01)
        assert run.status == "running" and run.assistant_message_id is None
        assert not any(event.type in {"message.completed", "run.succeeded"} for event in journal)
    finally:
        release.set()
        await operation


# RUN_025：持续错误实际耗尽三次预算，不用一次失败后成功替代。
async def test_RUN_025_exhaustion(workspace):
    created = await submit(workspace)

    class Provider:
        calls = 0

        async def stream_request(self, request):
            self.calls += 1
            yield "incomplete"
            raise TransientTaskError("UPSTREAM_TEMPORARY", "安全重试错误")

    provider = Provider()
    worker = runtime(workspace, provider)
    for attempt in range(1, 4):
        assert await worker.run_once()
        run, task, _ = await facts(workspace, created["run_id"])
        assert task.attempt == attempt
        if attempt < 3:
            assert run.status == "retry_waiting"
            # 测试时钟只推进queue，保持冻结Snapshot与deadline原值。
            async with workspace[1]() as session:
                saved = await session.get(TaskModel, created["task_id"])
                saved.available_at = queue.utc_now() - timedelta(seconds=1)
                await session.commit()
    assert run.status == task.state == "failed" and task.lease_expires_at is None
    assert run.assistant_message_id is None and provider.calls == 3
    assert not await worker.run_once()


# RUN_026：在Run创建前冻结合法小限额，分别断言到界成功/越界失败及UTF8字节。
@pytest.mark.parametrize(
    "field,limit,chunks,expected",
    [
        ("max_output_chars", 4, ["中文ab"], "succeeded"),
        ("max_output_chars", 3, ["中文ab"], "failed"),
        ("max_raw_deltas", 2, ["a", "b"], "succeeded"),
        ("max_raw_deltas", 1, ["a", "b"], "failed"),
        ("delta_buffer_bytes", 6, ["中文"], "succeeded"),
        ("delta_buffer_bytes", 5, ["中文"], "failed"),
    ],
)
async def test_RUN_026_frozen_boundaries(workspace, monkeypatch, field, limit, chunks, expected):
    from backend.application import session_runs

    monkeypatch.setitem(session_runs.EXECUTION_SNAPSHOT_LIMITS, field, limit)
    created = await submit(workspace)

    class Provider:
        async def stream_request(self, request):
            for chunk in chunks:
                yield chunk

    assert await runtime(workspace, Provider()).run_once()
    run, task, journal = await facts(workspace, created["run_id"])
    assert run.status == task.state == expected
    assert run.snapshot_json["execution"][field] == limit
    if expected == "failed":
        assert run.assistant_message_id is None and journal[-1].type == "run.failed"
    else:
        assert run.assistant_message_id


# SES_017：全部v2对象入口，对他人归属与不存在身份统一安全404。
def test_SES_017_owner_all_v2_endpoints(tmp_path):
    from uuid import uuid4

    with client_for(tmp_path) as client:
        seed_api(client)
        thread = client.post("/api/v2/threads", json={}).json()
        tid, bid = thread["thread_id"], thread["default_branch_id"]
        payload = dict(branch_id=bid, expected_version=0, content="owner fact")
        first = client.post(
            f"/api/v2/threads/{tid}/messages", json=payload, headers={"Idempotency-Key": "original"}
        ).json()
        rid = first["run_id"]
        owner = client.app.state.settings.owner_id
        for foreign in [True, False]:
            client.app.state.settings.owner_id = "foreign-owner" if foreign else owner
            thread_id, run_id = (tid, rid) if foreign else (str(uuid4()), str(uuid4()))
            base = f"/api/v2/threads/{thread_id}"
            operations = [
                ("GET", base, None),
                ("PATCH", base, {"archived": True}),
                ("GET", base + "/branches", None),
                (
                    "POST",
                    base + "/branches",
                    {"parent_branch_id": bid, "fork_message_id": first["message_id"]},
                ),
                ("POST", base + "/messages", payload),
                *[
                    ("GET", f"/api/v2/runs/{run_id}" + suffix, None)
                    for suffix in ["", "/events", "/events/stream", "/context"]
                ],
                *[
                    ("POST", f"/api/v2/runs/{run_id}/" + action, {})
                    for action in ["cancel", "retry", "regenerate"]
                ],
            ]
            for method, url, data in operations:
                response = client.request(
                    method, url, json=data, headers={"Idempotency-Key": "original"}
                )
                assert response.status_code == 404, (method, url, response.text)
                assert tid not in response.text and rid not in response.text
        client.app.state.settings.owner_id = owner
        detail = client.get(f"/api/v2/threads/{tid}").json()
        assert len(detail["messages"]) == len(detail["runs"]) == 1
        assert detail["thread"]["archived_at"] is None


# COMP_005/007：五种首次v2写分别独立升级；legacy关联请求必须显式成对模型。
@pytest.mark.parametrize("kind", ["patch", "branch", "message", "retry", "regenerate"])
def test_COMP_005_007_first_write_upgrade(tmp_path, kind):
    from backend.infrastructure.events.redis_notifier import RedisNotifier
    from backend.workers.runtime import WorkerRuntime

    with client_for(tmp_path) as client:
        seed_api(client)
        tid = client.post("/api/v1/threads", json={}).json()["thread_id"]
        source = client.post(
            f"/api/v1/threads/{tid}/messages", json={"content": "legacy input"}
        ).json()
        rid = source["run_id"]
        if kind == "regenerate":
            worker = WorkerRuntime(
                client.app.state.settings,
                client.app.state.session_factory,
                RedisNotifier(client.app.state.settings),
            )
            assert client.portal.call(worker.run_once)
            assert client.get(f"/api/v1/runs/{rid}").json()["status"] == "succeeded"
        else:
            client.post(f"/api/v1/runs/{rid}/cancel")
        old = client.get(f"/api/v2/threads/{tid}").json()
        assert old["thread"]["conversation_version"] == 1
        bid = old["branch"]["branch_id"]
        model = dict(model_profile_id="mock-default", model_profile_version=1)
        method, url, body = {
            "patch": ("PATCH", f"/api/v2/threads/{tid}", {"archived": False}),
            "branch": (
                "POST",
                f"/api/v2/threads/{tid}/branches",
                {"parent_branch_id": bid, "fork_message_id": source["message_id"]},
            ),
            "message": (
                "POST",
                f"/api/v2/threads/{tid}/messages",
                {
                    "branch_id": bid,
                    "content": "new input",
                    "expected_version": old["branch"]["version"],
                    **model,
                },
            ),
            "retry": ("POST", f"/api/v2/runs/{rid}/retry", model),
            "regenerate": ("POST", f"/api/v2/runs/{rid}/regenerate", model),
        }[kind]
        if kind in {"retry", "regenerate"}:
            for invalid in [{}, {"model_profile_id": "mock-default"}]:
                assert (
                    client.post(
                        url, json=invalid, headers={"Idempotency-Key": "invalid"}
                    ).status_code
                    == 422
                )
            assert (
                client.get(f"/api/v2/threads/{tid}").json()["thread"]["conversation_version"] == 1
            )
        invalid = client.request(
            method, url, json={**body, "unknown": True}, headers={"Idempotency-Key": "invalid"}
        )
        assert invalid.status_code == 422
        assert client.get(f"/api/v2/threads/{tid}").json()["thread"]["conversation_version"] == 1
        response = client.request(
            method, url, json=body, headers={"Idempotency-Key": "first-write"}
        )
        assert response.status_code in [200, 201], response.text
        current = client.get(f"/api/v2/threads/{tid}").json()
        assert current["thread"]["conversation_version"] == 2
        original = client.get(f"/api/v2/runs/{rid}").json()
        assert original["execution_schema_version"] == 1 and original["snapshot"] is None
        if kind in {"retry", "regenerate"}:
            target = response.json()
            assert target["message_id"] == source["message_id"]
            assert (
                client.get(f"/api/v2/runs/{target['run_id']}").json()["execution_schema_version"]
                == 2
            )
            assert (
                client.request(
                    method, url, json=body, headers={"Idempotency-Key": "first-write"}
                ).json()
                == target
            )


# COMP_006：旧字符串按原值读/无关更新；只有显式重命名使用新输入规则。
@pytest.mark.parametrize("title", ["", "   ", "  old title  "])
def test_COMP_006_legacy_titles(tmp_path, title):
    with client_for(tmp_path) as client:
        tid = client.post("/api/v1/threads", json={}).json()["thread_id"]
        mutate(
            tmp_path,
            "UPDATE threads SET title=:title WHERE thread_id=:tid",
            {"title": title, "tid": tid},
        )
        for archived in [True, False]:
            assert client.get(f"/api/v2/threads/{tid}").json()["thread"]["title"] == title
            assert (
                next(
                    t
                    for t in client.get("/api/v2/threads?include_archived=true").json()["threads"]
                    if t["thread_id"] == tid
                )["title"]
                == title
            )
            assert (
                client.patch(f"/api/v2/threads/{tid}", json={"archived": archived}).json()["title"]
                == title
            )
        assert (
            client.patch(f"/api/v2/threads/{tid}", json={"title": "  new title  "}).json()["title"]
            == "new title"
        )


# MOD_002：不可用配置/不存在版本不能部分创建事实。
def test_MOD_002_unavailable_profiles(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with client_for(tmp_path) as client:
        seed_api(client)

        async def prepare():
            async with client.app.state.session_factory() as session:
                await SQLModelProfileRepository(session).import_profiles(
                    [
                        profile(),
                        profile(profile_id="disabled", status="disabled", is_default=False),
                        real_profile(profile_id="missing-key", is_default=False),
                    ]
                )

        client.portal.call(prepare)
        thread = client.post("/api/v2/threads", json={}).json()
        for pid, version in [
            ("disabled", 1),
            ("missing-key", 1),
            ("not-found", 1),
            ("mock-default", 99),
        ]:
            response = client.post(
                f"/api/v2/threads/{thread['thread_id']}/messages",
                json={
                    "branch_id": thread["default_branch_id"],
                    "expected_version": 0,
                    "content": "no partial fact",
                    "model_profile_id": pid,
                    "model_profile_version": version,
                },
                headers={"Idempotency-Key": pid},
            )
            assert response.status_code in [409, 422]
        detail = client.get(f"/api/v2/threads/{thread['thread_id']}").json()
        assert detail["messages"] == detail["runs"] == [] and detail["branch"]["version"] == 0


# MOD_003：自动retry前改变默认/启用元数据；旧Snapshot不变，新Run使用新默认。
async def test_MOD_003_default_change_between_attempts(workspace, monkeypatch):
    settings, factory, *_ = workspace

    class Provider:
        def __init__(self):
            self.requests = []

        async def stream_request(self, request):
            self.requests.append(request)
            if len(self.requests) == 1:
                yield "OLD_ATTEMPT"
                raise TransientTaskError("UPSTREAM_TEMPORARY", "synthetic")
            yield "NEW_COMPLETE"

    provider = Provider()
    worker = runtime(workspace, provider)
    created = await submit(workspace)
    assert await worker.run_once()
    original, task, _ = await facts(workspace, created["run_id"])
    assert task.state == "retry_waiting"
    frozen = deepcopy(original.snapshot_json)
    async with factory() as session:
        await SQLModelProfileRepository(session).import_profiles(
            [
                profile(status="disabled", is_default=False),
                profile(
                    version=2,
                    model_name="new-default",
                    context_window_tokens=4096,
                    max_output_tokens=256,
                ),
            ]
        )
    monkeypatch.setattr(
        queue,
        "utc_now",
        lambda: task.available_at.replace(tzinfo=timezone.utc) + timedelta(milliseconds=1),
    )
    assert await worker.run_once()
    final, retried, _ = await facts(workspace, created["run_id"])
    assert final.status == "succeeded" and retried.generation == 2
    assert final.snapshot_json == frozen and provider.requests[-1].max_output_tokens == 1024
    later = await submit(workspace, "new default input", 2, "new-default")
    assert await worker.run_once()
    newer, _, _ = await facts(workspace, later["run_id"])
    assert newer.model_profile_version == 2 and provider.requests[-1].max_output_tokens == 256
    assert newer.snapshot_json["model_profile"]["model_name"] == "new-default"


# RUN_027：限额在Run创建前冻结；到界成功与超界失败均核对终态及租约。
@pytest.mark.parametrize("limit,expected", [(7, "succeeded"), (6, "failed")])
async def test_RUN_027_regular_events_boundary(workspace, monkeypatch, limit, expected):
    from backend.application import session_runs
    from backend.infrastructure.events.journal import RESERVED_EVENTS

    monkeypatch.setitem(session_runs.EXECUTION_SNAPSHOT_LIMITS, "max_regular_events", limit)
    created = await submit(workspace)
    assert await runtime(workspace, CaptureProvider()).run_once()
    run, task, journal = await facts(workspace, created["run_id"])
    assert run.status == task.state == expected
    assert len([event for event in journal if event.type not in RESERVED_EVENTS]) <= limit
    assert journal[-1].type == f"run.{expected}" and task.lease_expires_at is None
    if expected == "failed":
        assert run.last_error_code == "RUN_EVENT_LIMIT" and run.assistant_message_id is None


# RUN_028：deadline前一微秒可执行，到界即拒绝；取消同时存在时回收优先取消。
@pytest.mark.parametrize("cancel", [False, True])
async def test_RUN_028_deadline_exact_and_cancel_priority(workspace, monkeypatch, cancel):
    from backend.application.session_runs import cancel_session_run
    from backend.application.task_execution import ExecutionStopped, check_execution

    settings, factory, *_ = workspace
    created = await submit(workspace)
    async with factory() as session:
        task = await queue.claim_next_task(session, "deadline-worker", settings)
    deadline = task.deadline_at.replace(tzinfo=timezone.utc)
    # lease先到期时不能用deadline前一微秒假称合法；精确授权时间边界取min。
    boundary = min(deadline, task.lease_expires_at.replace(tzinfo=timezone.utc))
    monkeypatch.setattr(queue, "utc_now", lambda: boundary - timedelta(microseconds=1))
    assert await check_execution(factory, task.task_id, "deadline-worker", task.generation) > 0
    monkeypatch.setattr(queue, "utc_now", lambda: boundary)
    with pytest.raises(ExecutionStopped):
        await check_execution(factory, task.task_id, "deadline-worker", task.generation)
    if cancel:
        async with factory() as session:
            await cancel_session_run(session, settings, created["run_id"])
    monkeypatch.setattr(queue, "utc_now", lambda: deadline)
    async with factory() as session:
        await queue.requeue_expired(session)
    run, final, journal = await facts(workspace, created["run_id"])
    assert final.state == run.status == ("cancelled" if cancel else "failed")
    assert final.deadline_at.replace(tzinfo=timezone.utc) == deadline
    assert final.lease_expires_at is None and journal[-1].type == f"run.{run.status}"
