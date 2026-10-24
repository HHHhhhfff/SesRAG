"""SES_016/RUN_003/016/019/020/021：真实PG隔离专库中的锁与终态交错。"""

import argparse
import asyncio
import contextlib
import io
import json
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine as sync_engine
from sqlalchemy.engine import make_url

sys.path.insert(0, "/suite/tooling")
import importlib.util

spec = importlib.util.spec_from_file_location("db_admin", "/suite/tooling/db-admin.py")
admin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = admin
spec.loader.exec_module(admin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=["session", "run"], required=True)
    parser.add_argument("--expected-server-id", required=True)
    parser.add_argument("--expected-namespace", required=True)
    args = parser.parse_args()
    import pg_case_supplements as supplement

    from backend.config import Settings
    from backend.db.session import create_engine, create_session_factory
    from tests.integration import session_pg_probe as probe

    run_id = os.environ["WS_TEST_RUN_ID"]
    database = "sesrag_ws_migration_" + run_id[-8:]
    target = admin.validate_target(
        database_url=os.environ["DATABASE_URL"],
        run_id=run_id,
        database=database,
        namespace=args.expected_namespace,
        server_id=args.expected_server_id,
    )
    url = (
        make_url(os.environ["DATABASE_URL"])
        .set(database=database)
        .render_as_string(hide_password=False)
    )
    names = (
        ["creation_probe", "creation_edges"]
        if args.category == "session"
        else [
            "stale_and_publication_probe",
            "cancel_success_probe",
            "cancellation_reclaim_probe",
            "stale_all_writes",
            "commit_failure",
            "cancellation_skip_locked",
        ]
    )
    results = []
    for name in names:
        created = False
        log = io.StringIO()
        try:
            admin.execute("create", target)
            created = True
            sync = sync_engine(url)
            try:
                with sync.begin() as connection:
                    config = Config("/work/alembic.ini")
                    config.attributes["connection"] = connection
                    command.upgrade(config, "head")
            finally:
                sync.dispose()

            async def execute(scenario=name, capture=log):
                settings = Settings(
                    database_url=url,
                    redis_enabled=False,
                    task_lease_ttl=10,
                    task_heartbeat_interval=2,
                )
                engine = create_engine(settings)
                factory = create_session_factory(engine)
                try:
                    with contextlib.redirect_stdout(capture):
                        if scenario == "cancellation_reclaim_probe":
                            await getattr(probe, scenario)(factory, settings)
                        elif hasattr(probe, scenario):
                            await getattr(probe, scenario)(engine, factory, settings)
                        else:
                            await getattr(supplement, scenario)(engine, factory, settings)
                finally:
                    await engine.dispose()

            asyncio.run(execute())
            results.append({"name": name, "status": "passed", "actual": log.getvalue().strip()})
        except Exception as error:
            # 诊断不输出DSN或驱动堆栈；AssertionError文本来自固定合成测试。
            results.append(
                {
                    "name": name,
                    "status": "failed",
                    "actual": str(error)
                    if isinstance(error, AssertionError)
                    else type(error).__name__,
                }
            )
        finally:
            if created:
                admin.execute("drop", target)
    output = Path("/outputs") / args.category / "postgres-cases.json"
    output.write_text(
        json.dumps({"real_postgresql": True, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"status": "passed", "scenarios": len(results)}))


if __name__ == "__main__":
    main()
