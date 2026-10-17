"""分类可调用的真实PG场景，每次独立数据库且不SQL改写业务事实。"""

import asyncio
import json
import os
import sys
import traceback

from alembic import command
from alembic.config import Config
from pg_contract_scenarios import event_contracts
from pg_flush_scenarios import flush_boundaries
from pg_harness import Harness
from pg_queue_scenarios import (
    action_logs,
    commit_condition,
    crash_recovery,
    database_recovery,
    deadline,
    dual_worker,
    expired_final,
    heartbeat_rejection,
    lease_identity,
    locked_write_boundaries,
    long_lease,
    lost_lease,
    queue_boundaries,
    readiness,
    retry,
    signal_shutdown,
    stale_generation,
)
from pg_run_scenarios import (
    cancel_retry,
    cancellation,
    creation_rollback,
    final_flush_expiry,
    final_rollback,
    idempotency,
    journal,
    message_sequence,
    reentry,
    state_projection,
    terminal_race,
)
from sqlalchemy import create_engine as sync_engine
from sqlalchemy import text
from sqlalchemy.engine import make_url


async def main():
    scenario = sys.argv[1]
    token = os.environ["PG_SCENARIO_TOKEN"]
    assert len(token) == 8 and all(c in "0123456789abcdef" for c in token)
    url = make_url(os.environ["DATABASE_URL"])
    database = "sesrag_5a_" + token
    admin = sync_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {database}"))
    admin.dispose()
    url = url.set(database=database).render_as_string(hide_password=False)
    engine = sync_engine(url)
    with engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    engine.dispose()
    h = Harness(url)
    scenarios = {
        **{
            f"flush-{group}": lambda h, group=group: flush_boundaries(h, group)
            for group in ("queue", "failure", "events")
        },
        "event-contracts": event_contracts,
        "idempotency": idempotency,
        "reentry": reentry,
        "message-sequence": message_sequence,
        "creation-flush": lambda h: creation_rollback(h, "flush"),
        "creation-commit": lambda h: creation_rollback(h, "commit"),
        "final-rollback": final_rollback,
        "journal": journal,
        "dual-worker": dual_worker,
        "lease-identity": lease_identity,
        "stale-generation": stale_generation,
        "retry-success": lambda h: retry(h, "success"),
        "retry-exhausted": lambda h: retry(h, "exhausted"),
        "cancel-embed": lambda h: cancellation(h, "embed"),
        "cancel-search": lambda h: cancellation(h, "search"),
        "cancel-delta": lambda h: cancellation(h, "delta"),
        "cancel-retry": cancel_retry,
        "cancel-first": lambda h: terminal_race(h, "cancel"),
        "success-first": lambda h: terminal_race(h, "success"),
        "expired-final": expired_final,
        "final-flush-expiry": final_flush_expiry,
        "long-lease": long_lease,
        "signal-within": lambda h: signal_shutdown(h, "within"),
        "signal-outside": lambda h: signal_shutdown(h, "outside"),
        "crash-recovery": crash_recovery,
        "crash-exhausted": lambda h: crash_recovery(h, True),
        "deadline-running": lambda h: deadline(h, "running"),
        "deadline-retry": lambda h: deadline(h, "retry"),
        "queue-boundaries": queue_boundaries,
        "state-running": lambda h: state_projection(h, "running"),
        "state-retry": lambda h: state_projection(h, "retry_waiting"),
        "state-failed": lambda h: state_projection(h, "failed"),
    }
    scenarios.update(
        {
            "locked-write-boundaries": locked_write_boundaries,
            "heartbeat-rejection": heartbeat_rejection,
            "late-delta": lambda h: lost_lease(h, stage="delta"),
            "lost-lease": lost_lease,
            "late-error": lambda h: lost_lease(h, True),
            "commit-condition": commit_condition,
            "action-logs": action_logs,
            "database-recovery": database_recovery,
            "readiness": readiness,
        }
    )
    from pg_network_scenarios import network_scenarios

    scenarios.update(network_scenarios)
    from pg_document_scenarios import document_scenarios

    scenarios.update(document_scenarios)
    from pg_provider_scenarios import provider_scenarios

    scenarios.update(provider_scenarios)
    from pg_rag_scenarios import rag_scenarios

    scenarios.update(rag_scenarios)
    try:
        async with asyncio.timeout(65):
            await scenarios[scenario](h)
        print(
            "PG_SCENARIO:"
            + json.dumps(
                {
                    "status": "passed",
                    "scenario": scenario,
                    "database": database,
                    "assertions": h.assertions,
                    "trace": h.trace,
                    "logs": h.logs.rows,
                },
                default=str,
                ensure_ascii=False,
            )
        )
    except Exception as error:
        print(
            "PG_SCENARIO:"
            + json.dumps(
                {
                    "status": "failed",
                    "scenario": scenario,
                    "database": database,
                    "error_type": type(error).__name__,
                    "assertions": h.assertions,
                    "trace": h.trace,
                    "logs": h.logs.rows,
                },
                default=str,
                ensure_ascii=False,
            )
        )
        raise
    finally:
        await h.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
