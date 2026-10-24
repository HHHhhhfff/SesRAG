"""只管理本轮临时 PostgreSQL 专库；所有输出均为安全 JSON。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote, urlsplit

import psycopg
from psycopg import sql

RUN_PATTERN = re.compile(r"ws-(\d{8}t\d{6}z)-([0-9a-f]{8})\Z")
CATEGORIES = "env|session|context|model|run|workspace|compatibility|performance|quality"


class ToolError(RuntimeError):
    """只携带稳定错误码，防止驱动异常泄露连接凭据。"""


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        raise ToolError("ARGUMENTS_INVALID")


@dataclass(frozen=True)
class Target:
    run_id: str
    database: str
    namespace: str
    server_id: str
    connection_kwargs: dict = field(repr=False)


def validate_target(*, database_url, run_id, database, namespace, server_id):
    match = RUN_PATTERN.fullmatch(run_id or "")
    if match is None:
        raise ToolError("RUN_ID_REJECTED")
    try:
        datetime.strptime(match.group(1), "%Y%m%dt%H%M%Sz")
    except ValueError:
        raise ToolError("RUN_ID_REJECTED") from None
    suffix = match.group(2)
    if database not in {
        f"sesrag_session_probe_{suffix}",
        f"sesrag_ws_migration_{suffix}",
    }:
        raise ToolError("DATABASE_NAME_REJECTED")
    if not re.fullmatch(rf"sesrag-ws-{suffix}-({CATEGORIES})", namespace or ""):
        raise ToolError("NAMESPACE_REJECTED")
    if not re.fullmatch(r"[1-9][0-9]{8,19}", server_id or ""):
        raise ToolError("SERVER_ID_REJECTED")
    try:
        parsed = urlsplit(database_url)
        valid = (
            parsed.scheme in {"postgresql", "postgres", "postgresql+psycopg", "postgresql+asyncpg"}
            and parsed.hostname == "postgres"
            and parsed.port in {None, 5432}
            and unquote(parsed.path) == "/sesrag_workspace"
            and unquote(parsed.username or "") == "sesrag"
            and bool(parsed.password)
            and not parsed.query
            and not parsed.fragment
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ToolError("DATABASE_TARGET_REJECTED")
    return Target(
        run_id,
        database,
        namespace,
        server_id,
        {
            "host": "postgres",
            "port": 5432,
            "user": "sesrag",
            "password": unquote(parsed.password),
            "dbname": "postgres",
            "connect_timeout": 5,
            "options": "-c statement_timeout=5000 -c lock_timeout=2000",
        },
    )


def verify_server_identity(target, actual_server_id, actual_namespace):
    if str(actual_server_id) != target.server_id or actual_namespace != target.namespace:
        raise ToolError("SERVER_IDENTITY_MISMATCH")


def checked_connection(target, database="postgres"):
    connection = psycopg.connect(
        **{**target.connection_kwargs, "dbname": database}, autocommit=True
    )
    try:
        server = connection.execute(
            "SELECT system_identifier::text FROM pg_control_system()"
        ).fetchone()
        namespace = connection.execute("SHOW cluster_name").fetchone()
        identity = connection.execute("SELECT current_database(), current_user").fetchone()
        verify_server_identity(target, server[0], namespace[0])
        if identity != (database, "sesrag"):
            raise ToolError("SERVER_IDENTITY_MISMATCH")
    except BaseException:
        connection.close()
        raise
    return connection


def ownership_marker(target):
    material = "|".join((target.run_id, target.namespace, target.server_id, target.database))
    return "sesrag:test-002:" + hashlib.sha256(material.encode("ascii")).hexdigest()


def database_record(connection, target):
    row = connection.execute(
        "SELECT pg_get_userbyid(datdba), shobj_description(oid, 'pg_database') "
        "FROM pg_database WHERE datname = %s",
        (target.database,),
    ).fetchone()
    return None if row is None else {"owner": row[0], "marker": row[1]}


def object_count(target):
    with checked_connection(target, target.database) as connection:
        # 同时检查表、函数、类型、扩展和额外Schema，空库不只等于没有业务表。
        row = connection.execute(
            "WITH user_namespaces AS (SELECT oid, nspname FROM pg_namespace "
            "WHERE nspname !~ '^pg_' AND nspname <> 'information_schema') "
            "SELECT (SELECT count(*) FROM pg_class WHERE relnamespace IN "
            "(SELECT oid FROM user_namespaces)) + "
            "(SELECT count(*) FROM pg_proc WHERE pronamespace IN "
            "(SELECT oid FROM user_namespaces)) + "
            "(SELECT count(*) FROM pg_type WHERE typnamespace IN "
            "(SELECT oid FROM user_namespaces)) + "
            "(SELECT count(*) FROM pg_extension WHERE extname <> 'plpgsql') + "
            "(SELECT count(*) FROM user_namespaces WHERE nspname <> 'public')"
        ).fetchone()
        return row[0]


def validate_database_state(target, state, *, require_empty):
    if state["owner"] != "sesrag" or state["marker"] != ownership_marker(target):
        raise ToolError("DATABASE_OWNERSHIP_MISMATCH")
    if require_empty and state["object_count"] != 0:
        raise ToolError("DATABASE_NOT_EMPTY")


def inspect_database(connection, target, *, require_empty=False):
    state = database_record(connection, target)
    if state is None:
        return {"exists": False, "empty": None, "object_count": None}
    # 先验所有权再连接专库，不能用白名单前缀接管另一次手工创建的数据库。
    validate_database_state(target, {**state, "object_count": 0}, require_empty=False)
    count = object_count(target)
    validate_database_state(target, {**state, "object_count": count}, require_empty=require_empty)
    return {"exists": True, "empty": count == 0, "object_count": count}


def create_database(connection, target):
    if database_record(connection, target) is not None:
        raise ToolError("DATABASE_ALREADY_EXISTS")
    connection.execute(
        sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0").format(
            sql.Identifier(target.database), sql.Identifier("sesrag")
        )
    )
    connection.execute(
        sql.SQL("COMMENT ON DATABASE {} IS {}").format(
            sql.Identifier(target.database), sql.Literal(ownership_marker(target))
        )
    )
    return inspect_database(connection, target, require_empty=True)


def drop_database(connection, target):
    empty_required = target.database.startswith("sesrag_session_probe_")
    state = inspect_database(connection, target, require_empty=empty_required)
    if not state["exists"]:
        return state
    sessions = connection.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = %s", (target.database,)
    ).fetchone()[0]
    if sessions:
        raise ToolError("DATABASE_IN_USE")
    # 不使用FORCE或终止连接；连接占用由调用方退出后重试，最终由独占卷清理兜底。
    connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(target.database)))
    if database_record(connection, target) is not None:
        raise ToolError("DATABASE_DROP_NOT_CONFIRMED")
    return {"exists": False, "empty": None, "object_count": None}


def execute(action, target):
    if action not in {"create", "inspect", "drop", "self-test"}:
        raise ToolError("ARGUMENTS_INVALID")
    with checked_connection(target) as connection:
        if action == "create":
            return create_database(connection, target)
        if action == "inspect":
            return inspect_database(
                connection,
                target,
                require_empty=target.database.startswith("sesrag_session_probe_"),
            )
        if action == "drop":
            return drop_database(connection, target)
        created = False
        try:
            created_state = create_database(connection, target)
            created = True
            checked_state = inspect_database(connection, target, require_empty=True)
            dropped_state = drop_database(connection, target)
            created = False
            return {
                "created": created_state,
                "checked": checked_state,
                "deleted": dropped_state,
                "business_probe_executed": False,
            }
        finally:
            if created:
                drop_database(connection, target)


def main(argv=None):
    action = None
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("action", choices=("create", "inspect", "drop", "self-test"))
        parser.add_argument("--database")
        parser.add_argument("--expected-server-id", required=True)
        parser.add_argument("--expected-namespace", required=True)
        args = parser.parse_args(argv)
        action = args.action
        run_id = os.environ.get("WS_TEST_RUN_ID", "")
        database = args.database
        if action == "self-test":
            if database is not None:
                raise ToolError("ARGUMENTS_INVALID")
            database = "sesrag_session_probe_" + run_id[-8:]
        target = validate_target(
            database_url=os.environ.get("DATABASE_URL", ""),
            run_id=run_id,
            database=database,
            namespace=args.expected_namespace,
            server_id=args.expected_server_id,
        )
        result = {
            "schema_version": 1,
            "status": "passed",
            "run_id": run_id,
            "action": action,
            "database": database,
            "details": execute(action, target),
        }
        code = 0
    except Exception as error:
        result = {
            "schema_version": 1,
            "status": "failed",
            "action": action,
            "code": str(error) if isinstance(error, ToolError) else "DATABASE_OPERATION_FAILED",
        }
        code = 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
