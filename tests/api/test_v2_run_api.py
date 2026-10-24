import asyncio

from backend.db.models import ModelProfileModel
from tests.api.test_v2_session_api import client_for, mutate


def seed(client):
    async def insert():
        async with client.app.state.session_factory() as session:
            session.add(
                ModelProfileModel(
                    profile_id="mock-default",
                    version=1,
                    display_name="Mock",
                    provider_kind="mock",
                    model_name="mock",
                    generation_params={},
                    context_window_tokens=8192,
                    max_output_tokens=1024,
                    status="enabled",
                    is_default=True,
                    tokenizer_kind="mock",
                    tokenizer_version="1",
                    tokenizer_config={"safety_margin_tokens": 128, "summary_max_tokens": 512},
                )
            )
            await session.commit()

    asyncio.run(insert())


def create(client, thread, key="one", **overrides):
    return client.post(
        f"/api/v2/threads/{thread['thread_id']}/messages",
        json={
            "branch_id": thread["default_branch_id"],
            "content": "question",
            "expected_version": 0,
            **overrides,
        },
        headers={"Idempotency-Key": key},
    )


def test_create_snapshot_replay_before_archive_and_no_external_calls(tmp_path):
    with client_for(tmp_path) as client:
        seed(client)
        thread = client.post("/api/v2/threads", json={}).json()
        first = create(client, thread)
        assert first.status_code == 201, first.text
        result = first.json()
        detail = client.get(f"/api/v2/runs/{result['run_id']}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["snapshot"]["schema_version"] == 2
        assert detail.json()["context_plan"] is None
        assert client.get(f"/api/v2/runs/{result['run_id']}/context").json() == {
            "plan": None,
            "reason": "not_planned",
        }
        assert (
            client.get(f"/api/v2/runs/{result['run_id']}/context?generation=1").status_code == 404
        )
        assert client.get(f"/api/v1/runs/{result['run_id']}/events/stream").status_code == 409
        assert create(client, thread, "other").status_code == 409
        client.patch(f"/api/v2/threads/{thread['thread_id']}", json={"archived": True})
        replay = create(client, thread)
        assert replay.status_code == 200
        assert replay.json() == result
        assert create(client, thread, content="different").status_code == 409
        assert create(client, thread, "different-key").json()["code"] == "THREAD_ARCHIVED"
        events = client.get(f"/api/v2/runs/{result['run_id']}/events?limit=1").json()
        assert events["has_more"] is True and events["next_after_seq"] == 1
        assert events["events"][0]["schema_version"] == 2
        assert events["events"][0]["data"]["generation"] is None


def test_retry_reuses_input_and_immutable_creator_and_head_version(tmp_path):
    with client_for(tmp_path) as client:
        seed(client)
        thread = client.post("/api/v2/threads", json={}).json()
        initial = create(client, thread).json()
        rid = initial["run_id"]
        assert client.post(f"/api/v2/runs/{rid}/cancel").json()["status"] == "cancelled"
        retry = client.post(
            f"/api/v2/runs/{rid}/retry", json={}, headers={"Idempotency-Key": "retry"}
        )
        assert retry.status_code == 201, retry.text
        new = retry.json()
        assert new["message_id"] == initial["message_id"]
        assert new["branch_id"] == initial["branch_id"]
        page = client.get(f"/api/v2/threads/{thread['thread_id']}").json()
        assert len(page["messages"]) == 1
        assert page["messages"][0]["run_id"] == rid
        assert page["branch"]["version"] == 1
        assert client.get(f"/api/v2/runs/{new['run_id']}").json()["parent_run_id"] == rid
        assert (
            client.post(
                f"/api/v2/runs/{rid}/retry", json={}, headers={"Idempotency-Key": "retry"}
            ).json()
            == new
        )


def test_canonical_omitted_profile_and_owner_first_and_stale_head(tmp_path):
    with client_for(tmp_path) as client:
        seed(client)
        thread = client.post("/api/v2/threads", json={}).json()
        first = create(client, thread).json()
        assert (
            create(client, thread, model_profile_id="mock-default", model_profile_version=1).json()[
                "code"
            ]
            == "IDEMPOTENCY_CONFLICT"
        )
        client.post(f"/api/v2/runs/{first['run_id']}/cancel")
        assert create(client, thread, "new").json()["code"] == "BRANCH_HEAD_CHANGED"
        missing_key = client.post(
            f"/api/v2/threads/{thread['thread_id']}/messages",
            json={"branch_id": thread["default_branch_id"], "content": "x", "expected_version": 1},
        )
        assert missing_key.status_code == 422
        mutate(
            tmp_path,
            "UPDATE threads SET owner_id='another' WHERE thread_id=:id",
            {"id": thread["thread_id"]},
        )
        assert create(client, thread).status_code == 404
        assert client.get(f"/api/v2/runs/{first['run_id']}").status_code == 404


def test_legacy_projection_cancel_never_upgrade_and_explicit_profile(tmp_path):
    with client_for(tmp_path) as client:
        seed(client)
        thread = client.post("/api/v1/threads", json={}).json()
        old = client.post(
            f"/api/v1/threads/{thread['thread_id']}/messages", json={"content": "legacy"}
        ).json()
        rid = old["run_id"]
        view = client.get(f"/api/v2/runs/{rid}").json()
        assert view["legacy"] is True and view["snapshot"] is None
        assert client.post(f"/api/v2/runs/{rid}/cancel").json()["status"] == "cancelled"
        assert (
            client.get(f"/api/v2/threads/{thread['thread_id']}").json()["thread"][
                "conversation_version"
            ]
            == 1
        )
        assert (
            client.post(
                f"/api/v2/runs/{rid}/retry", json={}, headers={"Idempotency-Key": "retry"}
            ).json()["code"]
            == "MODEL_PROFILE_REQUIRED"
        )
        retry = client.post(
            f"/api/v2/runs/{rid}/retry",
            json={"model_profile_id": "mock-default", "model_profile_version": 1},
            headers={"Idempotency-Key": "retry"},
        )
        assert retry.status_code == 201, retry.text


def test_sse_header_priority_invalid_cursors_and_bounded_terminal_tail(tmp_path):
    with client_for(tmp_path) as client:
        seed(client)
        thread = client.post("/api/v2/threads", json={}).json()
        initial = create(client, thread).json()
        rid = initial["run_id"]
        client.post(f"/api/v2/runs/{rid}/cancel")
        events = client.get(f"/api/v2/runs/{rid}/events").json()["events"]
        assert client.get(f"/api/v2/runs/{rid}/events?after_seq=-1").status_code == 422
        assert client.get(f"/api/v2/runs/{rid}/events?after_seq=nope").status_code == 422
        url = f"/api/v2/runs/{rid}/events/stream?after_seq=999"
        for header in ["bad", "-1"]:
            replay = client.get(url, headers={"Last-Event-ID": header})
            assert "id: 1\n" in replay.text
        tail = client.get(url, headers={"Last-Event-ID": str(events[-1]["seq"])})
        assert tail.status_code == 200 and tail.text == ""


def test_retry_optional_body_and_profile_replay_before_unavailable(tmp_path):
    with client_for(tmp_path) as client:
        seed(client)
        thread = client.post("/api/v2/threads", json={}).json()
        first = create(client, thread).json()
        client.post(f"/api/v2/runs/{first['run_id']}/cancel")
        url = f"/api/v2/runs/{first['run_id']}/retry"
        retry = client.post(url, headers={"Idempotency-Key": "retry"})
        assert retry.status_code == 201, retry.text
        mutate(tmp_path, "UPDATE model_profiles SET is_default=0,status='disabled'")
        replay = client.post(url, json={}, headers={"Idempotency-Key": "retry"})
        assert replay.status_code == 200 and replay.json() == retry.json()
        refused = client.post(url, json={}, headers={"Idempotency-Key": "new-key"})
        assert refused.status_code == 409 and refused.json()["code"] == "MODEL_PROFILE_UNAVAILABLE"
