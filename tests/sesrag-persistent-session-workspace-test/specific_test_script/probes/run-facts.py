"""RUN_009/010：只读真实PG，用独立READ COMMITTED连接观察本例Run事实。"""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from uuid import UUID


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-server-id", required=True)
    parser.add_argument("--expected-namespace", required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("db_admin", "/suite/tooling/db-admin.py")
    admin = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = admin
    spec.loader.exec_module(admin)
    run_id = os.environ["WS_TEST_RUN_ID"]
    target = admin.validate_target(
        database_url=os.environ["DATABASE_URL"],
        run_id=run_id,
        database="sesrag_session_probe_" + run_id[-8:],
        namespace=args.expected_namespace,
        server_id=args.expected_server_id,
    )
    rid = json.loads(Path("/outputs/run/run-facts-input.json").read_text())["run_id"]
    assert str(UUID(rid)) == rid
    with admin.checked_connection(target, "sesrag_workspace") as connection:
        connection.execute("SET default_transaction_isolation = 'read committed'")
        # 一个新只读事务内观察整组，避免把跨快照的自然变化误认为原子性破坏。
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            row = connection.execute(
                "SELECT run_id, thread_id, status, assistant_message_id FROM runs WHERE run_id=%s",
                (rid,),
            ).fetchone()
            assert row is not None
            journal = connection.execute(
                "SELECT event_id, seq, type, payload_json, schema_version "
                "FROM run_events WHERE run_id=%s ORDER BY seq",
                (rid,),
            ).fetchall()
            assistants = connection.execute(
                "SELECT message_id FROM messages WHERE run_id=%s AND role='assistant'", (rid,)
            ).fetchall()
            task = connection.execute(
                "SELECT task_id, state, attempt, generation FROM tasks WHERE run_id=%s", (rid,)
            ).fetchone()
            input_message = connection.execute(
                "SELECT m.message_id,m.run_id FROM messages m "
                "JOIN runs r ON r.user_message_id=m.message_id WHERE r.run_id=%s",
                (rid,),
            ).fetchone()
            result = {
                "run_id": rid,
                "isolation": connection.execute("SHOW transaction_isolation").fetchone()[0],
                "status": row[2],
                "assistant_message_id": row[3],
                "assistant_ids": [item[0] for item in assistants],
                "user_message_id": input_message[0],
                "input_creator_run_id": input_message[1],
                "task": dict(zip(["task_id", "state", "attempt", "generation"], task, strict=True)),
                "events": [
                    dict(
                        zip(
                            ["event_id", "seq", "type", "data", "schema_version"], item, strict=True
                        )
                    )
                    for item in journal
                ],
            }
    Path("/outputs/run/run-facts.json").write_text(json.dumps(result, ensure_ascii=False))
    print(json.dumps({"status": "passed", "run_id": rid, "event_count": len(journal)}))


if __name__ == "__main__":
    main()
