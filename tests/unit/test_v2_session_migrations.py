import hashlib
import json

import pytest
from sqlalchemy import inspect, text

from tests.unit.test_foundation_migrations import migrate, migration_engine


def seed(connection):
    connection.execute(
        text(
            "INSERT INTO threads (thread_id,owner_id,title,next_message_seq,created_at,updated_at) "
            "VALUES ('thread','owner','history',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO messages (message_id,thread_id,seq,role,source,content,status,created_at) "
            "VALUES ('message','thread',1,'user','user_input','fact','completed',CURRENT_TIMESTAMP)"
        )
    )


def facts(connection):
    rows = connection.execute(
        text(
            "SELECT message_id,thread_id,seq,content,run_id,idempotency_key,created_at "
            "FROM messages ORDER BY message_id"
        )
    ).all()
    return hashlib.sha256(json.dumps([list(r) for r in rows], default=str).encode()).hexdigest()


def test_legacy_backfill_repeat_and_safe_roundtrip():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0003_chunk_locations")
        seed(connection)
        before = facts(connection)
        migrate(connection, "upgrade", "head")
        assert {
            "branches",
            "session_operations",
            "model_profiles",
            "context_plans",
            "conversation_summaries",
        } <= set(inspect(connection).get_table_names())
        assert (
            connection.execute(text("SELECT conversation_version FROM threads")).scalar_one() == 1
        )
        assert connection.execute(text("SELECT head_message_id,version FROM branches")).one() == (
            "message",
            1,
        )
        assert connection.execute(text("SELECT COUNT(*) FROM model_profiles")).scalar_one() == 2
        assert facts(connection) == before
        migrate(connection, "upgrade", "head")
        assert facts(connection) == before
        migrate(connection, "downgrade", "0003_chunk_locations")
        assert facts(connection) == before
        assert "branches" not in inspect(connection).get_table_names()


@pytest.mark.parametrize(
    "change,category",
    [
        ("UPDATE threads SET next_message_seq=0", "STALE_MESSAGE_COUNTER"),
        (
            "INSERT INTO runs (run_id,thread_id,user_message_id,status,snapshot_json,"
            "next_event_seq,created_at,updated_at) VALUES "
            "('r','thread','missing','queued','{}',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
            "RUN_INPUT_CONFLICT",
        ),
    ],
)
def test_upgrade_preflight_preserves_revision_and_original_facts(change, category):
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0003_chunk_locations")
        seed(connection)
        connection.execute(text(change))
        before = facts(connection)
        with pytest.raises(RuntimeError, match=category):
            migrate(connection, "upgrade", "head")
        assert facts(connection) == before
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0003_chunk_locations"
        )
        assert "branches" not in inspect(connection).get_table_names()


def test_downgrade_refuses_v2_facts_before_removing_any_table():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "head")
        connection.execute(
            text(
                "INSERT INTO threads (thread_id,owner_id,title,next_message_seq,"
                "conversation_version,created_at,updated_at) VALUES "
                "('t','o','v2',0,2,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        with pytest.raises(RuntimeError, match="V2_BUSINESS_FACTS"):
            migrate(connection, "downgrade", "0003_chunk_locations")
        assert "context_plans" in inspect(connection).get_table_names()
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0006_v2_run_guards"
        )


def seed_run(connection, identity, state):
    params = {"id": identity, "message": "m-" + identity, "task": "t-" + identity, "state": state}
    connection.execute(
        text(
            "INSERT INTO threads (thread_id,owner_id,title,next_message_seq,created_at,updated_at) "
            "VALUES (:id,'owner','old',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ),
        params,
    )
    connection.execute(
        text(
            "INSERT INTO messages (message_id,thread_id,seq,role,source,content,status,run_id,"
            "idempotency_key,created_at) VALUES (:message,:id,1,'user','user_input','原始事实',"
            "'completed',:id,:id,CURRENT_TIMESTAMP)"
        ),
        params,
    )
    connection.execute(
        text(
            "INSERT INTO runs (run_id,thread_id,user_message_id,primary_task_id,status,"
            "snapshot_json,"
            "next_event_seq,created_at,updated_at) VALUES (:id,:id,:message,:task,:state,"
            '\'{"model":"old"}\',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)'
        ),
        params,
    )
    task_state = "running" if state == "running" else state
    connection.execute(
        text(
            "INSERT INTO tasks (task_id,kind,run_id,state,attempt,max_attempts,generation,"
            "available_at,deadline_at,progress_json,created_at,updated_at) VALUES "
            "(:task,'run',:id,:task_state,1,3,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'{}',"
            "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ),
        {**params, "task_state": task_state},
    )
    connection.execute(
        text(
            "INSERT INTO run_events (event_id,run_id,seq,schema_version,type,payload_json,"
            "created_at) "
            "VALUES (:id,:id,1,1,'run.created','{}',CURRENT_TIMESTAMP)"
        ),
        params,
    )
    if state == "succeeded":
        connection.execute(
            text(
                "INSERT INTO messages (message_id,thread_id,seq,role,source,content,status,run_id,"
                "created_at) VALUES ('answer',:id,2,'assistant','assistant_generation',"
                "'old answer',"
                "'completed',:id,CURRENT_TIMESTAMP)"
            ),
            params,
        )
        connection.execute(
            text("UPDATE runs SET assistant_message_id='answer' WHERE run_id=:id"), params
        )
        connection.execute(
            text("UPDATE threads SET next_message_seq=2 WHERE thread_id=:id"), params
        )


def historic_hash(connection):
    values = {}
    for table in ("threads", "messages", "runs", "tasks", "run_events"):
        rows = connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).mappings().all()
        added = {
            "branch_id",
            "conversation_version",
            "parent_run_id",
            "operation_kind",
            "execution_schema_version",
            "context_plan_id",
            "model_profile_id",
            "model_profile_version",
        }
        values[table] = [{k: v for k, v in row.items() if k not in added} for row in rows]
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


def test_mixed_legacy_states_preserve_full_fact_hash_and_counts():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0003_chunk_locations")
        for state in ("queued", "running", "retry_waiting", "succeeded", "failed", "cancelled"):
            seed_run(connection, state, state)
        before = historic_hash(connection)
        migrate(connection, "upgrade", "head")
        assert historic_hash(connection) == before
        assert connection.execute(text("SELECT COUNT(*) FROM branches")).scalar_one() == 6
        assert (
            connection.execute(
                text(
                    "SELECT COUNT(*) FROM runs WHERE execution_schema_version=1 "
                    "AND operation_kind='initial'"
                )
            ).scalar_one()
            == 6
        )
        migrate(connection, "upgrade", "head")
        assert historic_hash(connection) == before
        migrate(connection, "downgrade", "0003_chunk_locations")
        assert historic_hash(connection) == before


@pytest.mark.parametrize(
    "mutation,category",
    [
        ("UPDATE messages SET role='assistant'", "RUN_INPUT_CONFLICT"),
        ("UPDATE messages SET thread_id='other'", "RUN_INPUT_CONFLICT"),
        ("DELETE FROM tasks", "RUN_TASK_CONFLICT"),
        ("UPDATE runs SET primary_task_id='wrong'", "RUN_TASK_CONFLICT"),
        ("UPDATE runs SET assistant_message_id='m-r'", "RUN_ASSISTANT_CONFLICT"),
        ("UPDATE runs SET status='unknown'", "INVALID_RUN_STATE"),
        ("UPDATE tasks SET state='unknown'", "INVALID_TASK_STATE"),
    ],
)
def test_preflight_identifies_conflicts_without_rewriting_facts(mutation, category):
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0003_chunk_locations")
        seed_run(connection, "r", "queued")
        connection.execute(text(mutation))
        before = historic_hash(connection)
        with pytest.raises(RuntimeError, match=category):
            migrate(connection, "upgrade", "head")
        assert historic_hash(connection) == before
        assert "branches" not in inspect(connection).get_table_names()


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE model_profiles SET model_name='imported' WHERE profile_id='mock-small'",
        "UPDATE model_profiles SET profile_id='custom' WHERE profile_id='mock-small'",
    ],
)
def test_custom_profile_downgrade_requires_explicit_export(change):
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "head")
        connection.execute(text(change))
        with pytest.raises(RuntimeError, match="CUSTOM_PROFILE_EXPORT_REQUIRED"):
            migrate(connection, "downgrade", "0003_chunk_locations")
        assert "context_plans" in inspect(connection).get_table_names()


@pytest.mark.parametrize("category", ["ACTIVE_BRANCH_CONFLICT", "RUN_TASK_CONFLICT"])
def test_preflight_rejects_duplicate_work_without_cancel_or_delete(category):
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0003_chunk_locations")
        seed_run(connection, "first", "queued")
        if category == "ACTIVE_BRANCH_CONFLICT":
            seed_run(connection, "second", "running")
            connection.execute(text("UPDATE runs SET thread_id='first' WHERE run_id='second'"))
            connection.execute(
                text("UPDATE messages SET thread_id='first',seq=2 WHERE message_id='m-second'")
            )
            connection.execute(
                text("UPDATE threads SET next_message_seq=2 WHERE thread_id='first'")
            )
        else:
            connection.execute(
                text(
                    "INSERT INTO tasks (task_id,kind,run_id,state,attempt,max_attempts,generation,"
                    "available_at,deadline_at,progress_json,created_at,updated_at) "
                    "SELECT 'duplicate',"
                    "kind,run_id,state,attempt,max_attempts,generation,available_at,deadline_at,"
                    "progress_json,created_at,updated_at FROM tasks"
                )
            )
        before = historic_hash(connection)
        with pytest.raises(RuntimeError, match=category):
            migrate(connection, "upgrade", "head")
        assert historic_hash(connection) == before
        assert "branches" not in inspect(connection).get_table_names()


@pytest.mark.parametrize("fact", ["schema2", "child", "shared_input", "operation"])
def test_downgrade_rejects_every_session_business_fact(fact):
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0003_chunk_locations")
        seed_run(connection, "old", "failed")
        migrate(connection, "upgrade", "head")
        if fact == "schema2":
            connection.execute(text("UPDATE runs SET execution_schema_version=2"))
        elif fact == "child":
            connection.execute(
                text(
                    "INSERT INTO branches (branch_id,thread_id,parent_branch_id,fork_message_id,"
                    "name,is_default,head_message_id,version,created_at,updated_at) SELECT 'child',"
                    "thread_id,branch_id,'m-old','child',false,'m-old',0,created_at,updated_at "
                    "FROM branches"
                )
            )
        elif fact == "shared_input":
            connection.execute(
                text(
                    "INSERT INTO runs (run_id,thread_id,user_message_id,status,snapshot_json,"
                    "next_event_seq,created_at,updated_at,branch_id) SELECT 'another',thread_id,"
                    "user_message_id,'failed',snapshot_json,0,created_at,updated_at,branch_id "
                    "FROM runs"
                )
            )
        else:
            connection.execute(
                text(
                    "INSERT INTO session_operations (operation_id,thread_id,idempotency_key,kind,"
                    "request_hash,result_branch_id,created_at) SELECT 'operation',thread_id,'key',"
                    "'branch','safe-hash',branch_id,created_at FROM branches"
                )
            )
        with pytest.raises(RuntimeError, match="V2_BUSINESS_FACTS"):
            migrate(connection, "downgrade", "0003_chunk_locations")
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0006_v2_run_guards"
        )


def test_v2_migration_chain_refuses_base_downgrade_even_empty():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "head")
        with pytest.raises(RuntimeError, match="BASE_DOWNGRADE_FORBIDDEN"):
            migrate(connection, "downgrade", "base")
        assert "model_profiles" in inspect(connection).get_table_names()
