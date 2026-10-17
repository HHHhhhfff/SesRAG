"""只在显式注入的隔离 PostgreSQL 数据库内检查固定迁移和事实保护。"""

import importlib.util
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, String, create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.db.models import ThreadModel


def migrate(connection, action, revision):
    config = Config("alembic.ini")
    config.attributes["connection"] = connection
    getattr(command, action)(config, revision)


def seed(connection):
    rows = {
        "threads": "('t','owner','fact',2,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
        "messages": "('m','t',1,'user','question','completed','r',NULL,'key',CURRENT_TIMESTAMP)",
        "runs": "('r','t','m',NULL,'task','queued','{}',0,NULL,NULL,"
        "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
        "tasks": "('task','run','r',NULL,'queued',0,3,CURRENT_TIMESTAMP,"
        "CURRENT_TIMESTAMP+INTERVAL '1 hour',NULL,0,NULL,'{}',NULL,NULL,"
        "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
        "run_events": "('e','r',1,1,'run.created','{}',CURRENT_TIMESTAMP)",
        "documents": "('d','owner','fact.txt','.txt',4,'hash','safe-key','uploaded',"
        "NULL,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
        "chunks": "('c','d','batch',1,'fact',0,4,NULL,CURRENT_TIMESTAMP)",
    }
    for table, values in rows.items():
        connection.execute(text(f"INSERT INTO {table} VALUES {values}"))
    connection.execute(
        text(
            "INSERT INTO messages VALUES ('a','t',2,'assistant','answer','completed',"
            "'r',NULL,NULL,CURRENT_TIMESTAMP)"
        )
    )


def snapshot(connection):
    result = {}
    for table in ("threads", "messages", "runs", "tasks", "run_events", "documents", "chunks"):
        columns = [
            c["name"] for c in inspect(connection).get_columns(table) if c["name"] != "source"
        ]
        result[table] = connection.execute(
            text(f"SELECT {','.join(columns)} FROM {table} ORDER BY 1")
        ).all()
    return result


def downgrade_interleaving(engine):
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA foundation_interleaving"))
        connection.execute(text("SET search_path TO foundation_interleaving, public"))
        migrate(connection, "upgrade", "0001_initial_demo")
    with engine.connect() as connection:
        connection.execute(text("SET search_path TO foundation_interleaving, public"))
        observed = []

        @event.listens_for(connection, "after_cursor_execute")
        def try_insert_after_empty_check(_connection, _cursor, statement, *_args):
            if statement != "SELECT 1 FROM threads LIMIT 1":
                return
            # 连接二在最后一张表已判空后真实 INSERT，不能依赖测试的虚构锁。
            with engine.connect() as writer:
                writer.execute(text("SET search_path TO foundation_interleaving, public"))
                writer.execute(text("SET lock_timeout TO '200ms'"))
                try:
                    writer.execute(
                        text(
                            "INSERT INTO threads VALUES ('late','owner','late fact',0,NULL,"
                            "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                        )
                    )
                    writer.commit()
                    observed.append("committed")
                except OperationalError as error:
                    assert error.orig.sqlstate == "55P03"
                    writer.rollback()
                    observed.append("blocked")
            assert observed == ["blocked"], "late INSERT committed after empty check"

        spec = importlib.util.spec_from_file_location(
            "initial_revision", Path("migrations/versions/0001_initial_demo.py")
        )
        revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(revision)
        try:
            with Operations.context(MigrationContext.configure(connection)):
                revision.downgrade()
            assert observed == ["blocked"]
        finally:
            # 测试卸载事务回滚，仍可验证并保留空库，不影响其他 Schema。
            connection.rollback()
    print("PASS: PG second connection INSERT after empty check is blocked until downgrade ends")


def schema_catalog(connection, schema):
    tables = ("threads", "messages", "runs", "tasks", "run_events", "documents", "chunks")
    result = {}
    for table in tables:
        columns = connection.execute(
            text(
                "SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,"
                "pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a "
                "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
                "WHERE n.nspname=:schema AND c.relname=:table AND a.attnum>0 "
                "AND NOT a.attisdropped ORDER BY a.attnum"
            ),
            {"schema": schema, "table": table},
        ).all()
        constraints = connection.execute(
            text(
                "SELECT con.conname,con.contype,pg_get_constraintdef(con.oid) "
                "FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname=:schema AND c.relname=:table ORDER BY con.conname"
            ),
            {"schema": schema, "table": table},
        ).all()
        indexes = connection.execute(
            text(
                "SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=:schema "
                "AND tablename=:table ORDER BY indexname"
            ),
            {"schema": schema, "table": table},
        ).all()

        def normalized(rows):
            return [tuple(str(v).replace(f"{schema}.", "") for v in row) for row in rows]

        result[table] = (normalized(columns), normalized(constraints), normalized(indexes))
    return result


def schema_equivalence(engine):
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA foundation_schema_compare"))
        connection.execute(text("SET search_path TO foundation_schema_compare, public"))
        migrate(connection, "upgrade", "0001_initial_demo")
        baseline = schema_catalog(connection, "public")
        fixed = schema_catalog(connection, "foundation_schema_compare")
        assert baseline == fixed, f"frozen baseline schema differs: {baseline!r} != {fixed!r}"
    print(
        "PASS: old-image metadata vs fixed 0001 all seven tables "
        "columns/types/null/defaults/constraints/indexes identical"
    )


def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"))
        connection.execute(text("CREATE SCHEMA foundation_normal"))
        connection.execute(text("SET search_path TO foundation_normal, public"))
        column = Column("future_probe_field", String(20))
        ThreadModel.__table__.append_column(column)
        try:
            migrate(connection, "upgrade", "0001_initial_demo")
        finally:
            ThreadModel.__table__._columns.remove(column)
        assert "future_probe_field" not in {
            c["name"] for c in inspect(connection).get_columns("threads")
        }
        seed(connection)
        before = snapshot(connection)
        migrate(connection, "upgrade", "head")
        assert snapshot(connection) == before
        assert connection.execute(
            text("SELECT source FROM messages ORDER BY message_id")
        ).scalars().all() == ["assistant_generation", "user_input"]
        assert (
            connection.execute(text("SELECT source FROM documents")).scalar_one() == "local_upload"
        )
        migrate(connection, "upgrade", "head")
        constraints = {c["name"] for c in inspect(connection).get_unique_constraints("messages")}
        assert "uq_messages_thread_idempotency" in constraints
        assert "ck_tasks_kind_target" in {
            c["name"] for c in inspect(connection).get_check_constraints("tasks")
        }
        assert "uq_messages_assistant_run" in {
            c["name"] for c in inspect(connection).get_indexes("messages")
        }
        for sql in (
            "INSERT INTO messages SELECT 'duplicate',thread_id,3,role,content,status,"
            "run_id,citations_json,idempotency_key,created_at,source "
            "FROM messages WHERE message_id='m'",
            "INSERT INTO messages SELECT 'duplicate',thread_id,3,role,content,status,"
            "run_id,citations_json,idempotency_key,created_at,source "
            "FROM messages WHERE message_id='a'",
            "UPDATE tasks SET document_id='d' WHERE task_id='task'",
        ):
            try:
                with connection.begin_nested():
                    connection.execute(text(sql))
            except IntegrityError:
                pass
            else:
                raise AssertionError("integrity constraint did not reject invalid fact")
        migrate(connection, "downgrade", "0001_initial_demo")
        assert snapshot(connection) == before
        assert (
            connection.execute(text("SELECT source FROM documents")).scalar_one() == "local_upload"
        )
        connection.execute(
            text(
                "INSERT INTO messages (message_id,thread_id,seq,role,content,status,created_at) "
                "VALUES ('old-writer','t',3,'assistant','old answer','completed',CURRENT_TIMESTAMP)"
            )
        )
        before = snapshot(connection)
        migrate(connection, "upgrade", "head")
        assert snapshot(connection) == before
        assert (
            connection.execute(
                text("SELECT source FROM messages WHERE message_id='old-writer'")
            ).scalar_one()
            == "assistant_generation"
        )
        try:
            with connection.begin_nested():
                migrate(connection, "downgrade", "base")
        except RuntimeError as error:
            assert "NONEMPTY_DATABASE" in str(error)
        else:
            raise AssertionError("nonempty initial downgrade was allowed")
        assert snapshot(connection) == before
    print(
        "PASS: fresh PG, frozen 0001, all seven fact tables, constraints, "
        "repeat upgrade, safe downgrade/reupgrade"
    )
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA foundation_conflict"))
        connection.execute(text("SET search_path TO foundation_conflict, public"))
        migrate(connection, "upgrade", "0001_initial_demo")
        seed(connection)
        connection.execute(
            text(
                "INSERT INTO messages SELECT 'duplicate',thread_id,3,role,content,status,"
                "run_id,citations_json,idempotency_key,created_at "
                "FROM messages WHERE message_id='m'"
            )
        )
        try:
            with connection.begin_nested():
                migrate(connection, "upgrade", "head")
        except RuntimeError as error:
            assert "MESSAGE_IDEMPOTENCY_CONFLICT" in str(error)
        else:
            raise AssertionError("conflicting migration was allowed")
        assert connection.execute(text("SELECT COUNT(*) FROM messages")).scalar_one() == 3
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0001_initial_demo"
        )
    print("PASS: conflicting old PG upgrade aborted and preserved all original facts")
    downgrade_interleaving(engine)
    schema_equivalence(engine)
    engine.dispose()


if __name__ == "__main__":
    main()
