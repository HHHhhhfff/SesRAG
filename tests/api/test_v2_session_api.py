from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from backend.app import create_app
from backend.config import Settings


def client_for(tmp_path):
    return TestClient(
        create_app(
            Settings(
                database_url=f"sqlite+aiosqlite:///{tmp_path / 'session.db'}",
                upload_dir=str(tmp_path / "uploads"),
                auto_create_schema=True,
                redis_enabled=False,
            )
        )
    )


def mutate(tmp_path, statement, params=None):
    engine = create_engine(f"sqlite:///{tmp_path / 'session.db'}")
    with engine.begin() as connection:
        connection.execute(text(statement), params or {})
    engine.dispose()


def test_v2_create_default_branch_and_v1_version_boundary(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/api/v2/threads", json={"title": "  workspace  "})
        assert response.status_code == 201
        thread = response.json()
        assert thread["title"] == "workspace"
        assert thread["conversation_version"] == 2
        detail = client.get(f"/api/v2/threads/{thread['thread_id']}").json()
        assert detail["branch"]["branch_id"] == thread["default_branch_id"]
        assert detail["branch"]["version"] == 0
        assert detail["messages"] == []
        assert client.get("/api/v1/threads").json() == []
        legacy = client.get(f"/api/v1/threads/{thread['thread_id']}")
        assert legacy.status_code == 409
        assert legacy.json()["code"] == "API_VERSION_REQUIRED"


def test_legacy_read_no_upgrade_active_write_guard_and_title_preservation(tmp_path):
    with client_for(tmp_path) as client:
        thread = client.post("/api/v1/threads", json={"title": "  "}).json()
        tid = thread["thread_id"]
        detail = client.get(f"/api/v2/threads/{tid}").json()
        assert detail["thread"]["conversation_version"] == 1
        assert detail["thread"]["title"] == ""
        created = client.post(
            f"/api/v1/threads/{tid}/messages",
            json={"content": "input"},
            headers={"Idempotency-Key": "old"},
        )
        assert created.status_code == 201
        busy = client.post(f"/api/v1/threads/{tid}/messages", json={"content": "second"})
        assert busy.status_code == 409
        assert busy.json()["code"] == "BRANCH_BUSY"
        patch = client.patch(f"/api/v2/threads/{tid}", json={"archived": True})
        assert patch.status_code == 409
        assert patch.json()["code"] == "LEGACY_RUN_ACTIVE"
        assert client.get(f"/api/v2/threads/{tid}").json()["thread"]["conversation_version"] == 1
        run_id = created.json()["run_id"]
        assert client.post(f"/api/v1/runs/{run_id}/cancel").status_code == 200
        patch = client.patch(f"/api/v2/threads/{tid}", json={"archived": True})
        assert patch.status_code == 200
        assert patch.json()["title"] == ""
        assert patch.json()["conversation_version"] == 2
        assert client.get(f"/api/v1/runs/{run_id}").status_code == 200


def test_fork_identity_replay_before_archive_and_inherited_path(tmp_path):
    with client_for(tmp_path) as client:
        tid = client.post("/api/v1/threads", json={}).json()["thread_id"]
        message = client.post(f"/api/v1/threads/{tid}/messages", json={"content": "first"}).json()
        detail = client.get(f"/api/v2/threads/{tid}").json()
        parent = detail["branch"]["branch_id"]
        payload = {"parent_branch_id": parent, "fork_message_id": message["message_id"]}
        active = client.post(
            f"/api/v2/threads/{tid}/branches", json=payload, headers={"Idempotency-Key": "fork"}
        )
        assert active.status_code == 422
        assert client.get(f"/api/v2/threads/{tid}").json()["thread"]["conversation_version"] == 1
        client.post(f"/api/v1/runs/{message['run_id']}/cancel")
        first = client.post(
            f"/api/v2/threads/{tid}/branches", json=payload, headers={"Idempotency-Key": "fork"}
        )
        assert first.status_code == 201
        child = first.json()
        assert child["head_message_id"] == message["message_id"]
        assert child["version"] == 0
        second = client.post(
            f"/api/v2/threads/{tid}/branches", json=payload, headers={"Idempotency-Key": "other"}
        )
        assert second.status_code == 201
        assert second.json()["branch_id"] != child["branch_id"]
        page = client.get(f"/api/v2/threads/{tid}", params={"branch_id": child["branch_id"]}).json()
        assert [m["content"] for m in page["messages"]] == ["first"]
        assert len(page["branch_path"]) == 2
        client.patch(f"/api/v2/threads/{tid}", json={"archived": True})
        replay = client.post(
            f"/api/v2/threads/{tid}/branches", json=payload, headers={"Idempotency-Key": "fork"}
        )
        assert replay.status_code == 200
        assert replay.json() == child
        conflict = client.post(
            f"/api/v2/threads/{tid}/branches",
            json={**payload, "name": "changed"},
            headers={"Idempotency-Key": "fork"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_v2_keyset_pages_and_archive_filter(tmp_path):
    with client_for(tmp_path) as client:
        ids = [
            client.post("/api/v2/threads", json={"title": str(i)}).json()["thread_id"]
            for i in range(4)
        ]
        client.patch(f"/api/v2/threads/{ids[0]}", json={"archived": True})
        first = client.get("/api/v2/threads", params={"limit": 2}).json()
        assert len(first["threads"]) == 2 and first["has_more"]
        second = client.get(
            "/api/v2/threads", params={"limit": 2, "cursor": first["next_cursor"]}
        ).json()
        assert len(second["threads"]) == 1 and not second["has_more"]
        assert len({t["thread_id"] for t in first["threads"] + second["threads"]}) == 3
        assert len(client.get("/api/v2/threads?include_archived=true").json()["threads"]) == 4
        assert client.get("/api/v2/threads?cursor=bad").status_code == 422
        assert client.get("/api/v2/threads?unexpected=secret").status_code == 422


def test_v1_all_run_endpoints_guard_schema_after_owner_before_sse(tmp_path):
    with client_for(tmp_path) as client:
        tid = client.post("/api/v1/threads", json={}).json()["thread_id"]
        rid = client.post(f"/api/v1/threads/{tid}/messages", json={"content": "input"}).json()[
            "run_id"
        ]
        mutate(
            tmp_path, "UPDATE runs SET execution_schema_version=2 WHERE run_id=:rid", {"rid": rid}
        )
        for suffix, method in (
            ("", "get"),
            ("/events", "get"),
            ("/events/stream", "get"),
            ("/cancel", "post"),
        ):
            result = getattr(client, method)(f"/api/v1/runs/{rid}{suffix}")
            assert result.status_code == 409
            assert result.json()["code"] == "API_VERSION_REQUIRED"
        mutate(tmp_path, "UPDATE threads SET owner_id='other' WHERE thread_id=:tid", {"tid": tid})
        for suffix, method in (
            ("", "get"),
            ("/events", "get"),
            ("/events/stream", "get"),
            ("/cancel", "post"),
        ):
            assert getattr(client, method)(f"/api/v1/runs/{rid}{suffix}").status_code == 404
        for prefix in ("/api/v1", "/api/v2"):
            assert client.get(f"{prefix}/threads/{tid}").status_code == 404


def test_branch_cross_thread_and_invisible_path_and_required_key(tmp_path):
    with client_for(tmp_path) as client:
        tids = [client.post("/api/v1/threads", json={}).json()["thread_id"] for _ in range(2)]
        messages = []
        branches = []
        for tid in tids:
            result = client.post(
                f"/api/v1/threads/{tid}/messages", json={"content": "input"}
            ).json()
            client.post(f"/api/v1/runs/{result['run_id']}/cancel")
            messages.append(result["message_id"])
            branches.append(client.get(f"/api/v2/threads/{tid}").json()["branch"]["branch_id"])
        payload = {"parent_branch_id": branches[0], "fork_message_id": messages[0]}
        endpoint = f"/api/v2/threads/{tids[0]}/branches"
        assert client.post(endpoint, json=payload).status_code == 422
        foreign = client.post(
            endpoint,
            json={**payload, "fork_message_id": messages[1]},
            headers={"Idempotency-Key": "foreign"},
        )
        assert foreign.status_code == 404
        assert (
            client.get(f"/api/v2/threads/{tids[0]}").json()["thread"]["conversation_version"] == 1
        )
        assert (
            client.get(f"/api/v2/threads/{tids[0]}", params={"branch_id": branches[1]}).status_code
            == 404
        )


def test_detail_message_pagination_and_legacy_branch_head_after_worker(tmp_path):
    import asyncio

    from backend.application.task_execution import complete_run
    from backend.infrastructure.queue.postgres_queue import claim_next_task

    with client_for(tmp_path) as client:
        tid = client.post("/api/v1/threads", json={}).json()["thread_id"]
        first = client.post(f"/api/v1/threads/{tid}/messages", json={"content": "first"}).json()

        async def finish():
            async with client.app.state.session_factory() as session:
                task = await claim_next_task(session, "worker", client.app.state.settings)
                await complete_run(session, task.task_id, "worker", task.generation, "answer", [])

        asyncio.run(finish())
        second = client.post(f"/api/v1/threads/{tid}/messages", json={"content": "second"}).json()
        latest = client.get(f"/api/v2/threads/{tid}", params={"limit": 2}).json()
        assert latest["branch"]["version"] == 3
        assert latest["branch"]["head_message_id"] == second["message_id"]
        assert [m["content"] for m in latest["messages"]] == ["answer", "second"]
        assert latest["next_before_seq"] == 2 and latest["has_more"]
        older = client.get(f"/api/v2/threads/{tid}", params={"before_seq": 2, "limit": 2}).json()
        assert [m["message_id"] for m in older["messages"]] == [first["message_id"]]
        assert older["next_before_seq"] is None and not older["has_more"]
        assert older["active_run_id"] == second["run_id"]
        assert older["recent_run_id"] == second["run_id"]
