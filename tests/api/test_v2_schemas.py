"""v2 请求边界：禁止伪造服务端事实，Profile 选择必须成对。"""

import importlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError


def schema(module, name):
    return getattr(importlib.import_module(f"backend.api.schemas.v2.{module}"), name)


def test_message_rejects_unpaired_profile_blank_and_server_fields():
    model = schema("threads", "MessageCreate")
    valid = {
        "branch_id": "00000000-0000-4000-8000-000000000001",
        "content": "  question  ",
        "expected_version": 0,
    }
    assert model(**valid).content == "  question  "
    for changes in [
        {"content": " \n\t"},
        {"content": "x" * 20001},
        {"expected_version": -1},
        {"model_profile_id": "mock"},
        {"model_profile_version": 1},
        {"model_profile_id": None},
        {"model_profile_version": True},
        {"operation_kind": "initial"},
        {"parent_run_id": valid["branch_id"]},
        {"owner_id": "other"},
        {"expected_version": True},
    ]:
        with pytest.raises(ValidationError):
            model(**(valid | changes))
    assert (
        model(
            **(valid | {"model_profile_id": "mock", "model_profile_version": 2})
        ).model_profile_version
        == 2
    )


def test_titles_names_patch_and_operation_profile_validation():
    create = schema("threads", "ThreadCreate")
    patch = schema("threads", "ThreadPatch")
    branch = schema("threads", "BranchCreate")
    operation = schema("runs", "RunOperationCreate")
    assert create(title="  test  ").title == "test"
    assert create(title=" " + "x" * 200 + " ").title == "x" * 200
    assert create().title == "新会话"
    assert patch(archived=False).archived is False
    identity = "00000000-0000-4000-8000-000000000001"
    assert (
        branch(parent_branch_id=identity, fork_message_id=identity, name="  fork ").name == "fork"
    )
    assert (
        branch(parent_branch_id=identity, fork_message_id=identity, name=" " + "x" * 80 + " ").name
        == "x" * 80
    )
    for model, values in [
        (create, {"title": "  "}),
        (create, {"title": "x" * 201}),
        (patch, {}),
        (patch, {"title": None}),
        (patch, {"archived": "false"}),
        (branch, {"parent_branch_id": identity, "fork_message_id": identity, "name": " "}),
        (operation, {"model_profile_id": "mock"}),
        (operation, {"model_profile_id": "mock", "model_profile_version": 0}),
        (operation, {"parent_run_id": identity}),
    ]:
        with pytest.raises(ValidationError):
            model(**values)
    assert operation().model_dump(exclude_unset=True) == {}


@pytest.mark.parametrize("stored_title", ["", " \t ", "  legacy title  "])
@pytest.mark.parametrize("conversation_version", [1, 2])
def test_thread_response_preserves_legacy_title_after_metadata_upgrade(
    stored_title, conversation_version
):
    # 新写入限制不能阻止旧事实读取，元数据升级也不能隐式改名。
    response = schema("threads", "ThreadSummary")(
        thread_id="legacy-thread",
        owner_id="local-user",
        title=stored_title,
        default_branch_id="default-branch",
        conversation_version=conversation_version,
        archived_at=None,
        created_at="2026-10-19T00:00:00Z",
        updated_at="2026-10-19T00:00:00Z",
    )
    assert response.title == stored_title
    assert response.model_dump(mode="json")["title"] == stored_title


@pytest.mark.parametrize("title", ["", " ", "\t\n", "x" * 201])
def test_new_v2_create_and_rename_keep_strict_title_boundary(title):
    for model in [schema("threads", "ThreadCreate"), schema("threads", "ThreadPatch")]:
        with pytest.raises(ValidationError):
            model(title=title)


def test_pagination_defaults_and_limits():
    for name, default, maximum in [("ThreadListQuery", 50, 200), ("ThreadDetailQuery", 50, 200)]:
        model = schema("threads", name)
        assert model().limit == default
        assert model(limit=maximum).limit == maximum
        for value in [0, maximum + 1]:
            with pytest.raises(ValidationError):
                model(limit=value)
    events = schema("runs", "EventListQuery")
    assert events().model_dump() == {"after_seq": 0, "limit": 200}
    assert events(limit=1000).limit == 1000
    with pytest.raises(ValidationError):
        events(after_seq=-1)
    with pytest.raises(ValidationError):
        schema("context", "ContextQuery")(generation=0)


def test_event_response_validates_version_and_exact_payload():
    model = schema("runs", "EventResponse")
    event = {
        "schema_version": 1,
        "event_id": "event",
        "run_id": "run",
        "seq": 1,
        "type": "answer.delta",
        "occurred_at": "2026-10-19T00:00:00Z",
        "data": {"text": "legacy"},
    }
    assert model(**event).data == {"text": "legacy"}
    with pytest.raises(ValidationError):
        model(**(event | {"schema_version": 2}))
    current = event | {
        "schema_version": 2,
        "data": {"text": "v2", "task_id": "task", "attempt": 1, "generation": 1},
    }
    assert model(**current).data["generation"] == 1
    for change in [
        {"type": "run.started"},
        {"schema_version": 1},
        {"data": current["data"] | {"secret": "sentinel"}},
        {"data": current["data"] | {"generation": None}},
    ]:
        with pytest.raises(ValidationError):
            model(**(current | change))


def test_json_contract_samples_also_validate_backend_dtos():
    samples = json.loads(
        (Path(__file__).parents[1] / "demo-smoke/tooling/v2-contract-samples.json").read_text(
            encoding="utf-8"
        )
    )
    for module, name, key in [
        ("threads", "ThreadSummary", "thread"),
        ("threads", "Branch", "branch"),
        ("threads", "MessageResponse", "message"),
        ("context", "ContextPlan", "context_plan"),
        ("context", "ContextPlanSummary", "context_summary"),
        ("context", "SummaryMetadata", "summary"),
        ("runs", "RunResponse", "run"),
    ]:
        model = schema(module, name)
        assert model.model_validate(samples[key])
        with pytest.raises(ValidationError):
            model.model_validate(samples[key] | {"secret": "sentinel"})
    model = schema("runs", "EventResponse")
    for seq, (event_type, data) in enumerate(samples["event_payloads"].items(), 1):
        event = {
            "schema_version": 2,
            "event_id": "event",
            "run_id": "run",
            "seq": seq,
            "type": event_type,
            "occurred_at": "2026-10-19T00:00:00Z",
            "data": data,
        }
        assert model.model_validate(event).data == data
        with pytest.raises(ValidationError):
            model.model_validate(event | {"data": data | {"secret": "sentinel"}})
