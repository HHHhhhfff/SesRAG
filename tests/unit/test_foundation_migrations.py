from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Column, String, create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.db.models import ThreadModel


def migration_engine():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def skip_postgres_extension(_conn, _cursor, statement, parameters, _context, _many):
        # SQLite 仅替换不支持的扩展安装，其余迁移 DDL/DML 真实执行。
        if statement == "CREATE EXTENSION IF NOT EXISTS vector":
            statement = "SELECT 1"
        return statement, parameters

    return engine


def migrate(connection, action, revision):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = connection
    getattr(command, action)(config, revision)


def seed(connection):
    connection.execute(
        text(
            "INSERT INTO threads (thread_id,owner_id,title,next_message_seq,created_at,updated_at) "
            "VALUES ('thread','owner','history',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO messages (message_id,thread_id,seq,role,content,status,created_at) "
            "VALUES ('message','thread',1,'user','fact','completed',CURRENT_TIMESTAMP)"
        )
    )


def test_initial_migration_is_frozen_against_new_orm_columns():
    column = Column("future_field", String(30))
    ThreadModel.__table__.append_column(column)
    try:
        with migration_engine().begin() as connection:
            migrate(connection, "upgrade", "0001_initial_demo")
            assert "future_field" not in {
                c["name"] for c in inspect(connection).get_columns("threads")
            }
    finally:
        ThreadModel.__table__._columns.remove(column)


def test_integrity_upgrade_downgrade_preserves_existing_facts():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0001_initial_demo")
        seed(connection)
        migrate(connection, "upgrade", "head")
        assert connection.execute(text("SELECT content,source FROM messages")).one() == (
            "fact",
            "user_input",
        )
        migrate(connection, "upgrade", "head")
        migrate(connection, "downgrade", "0001_initial_demo")
        assert connection.execute(text("SELECT content,source FROM messages")).one() == (
            "fact",
            "user_input",
        )
        migrate(connection, "upgrade", "head")
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO tasks (task_id,kind,state,attempt,max_attempts,generation,"
                    "available_at,deadline_at,progress_json,created_at,updated_at) "
                    "VALUES ('bad','run','queued',0,3,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,"
                    "'{}',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                )
            )


def test_downgraded_old_writer_can_create_message_and_reupgrade_source():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0001_initial_demo")
        seed(connection)
        migrate(connection, "upgrade", "head")
        migrate(connection, "downgrade", "0001_initial_demo")
        connection.execute(
            text(
                "INSERT INTO messages (message_id,thread_id,seq,role,content,status,created_at) "
                "VALUES ('old-writer','thread',2,'assistant','answer','completed',"
                "CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(text("UPDATE threads SET next_message_seq=2 WHERE thread_id='thread'"))
        migrate(connection, "upgrade", "head")
        assert (
            connection.execute(
                text("SELECT source FROM messages WHERE message_id='old-writer'")
            ).scalar_one()
            == "assistant_generation"
        )


def test_integrity_conflict_aborts_without_deleting_message_history():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0001_initial_demo")
        seed(connection)
        connection.execute(text("UPDATE messages SET idempotency_key='duplicate'"))
        connection.execute(
            text(
                "INSERT INTO messages (message_id,thread_id,seq,role,content,status,"
                "idempotency_key,created_at) VALUES ('other','thread',2,'user','second fact',"
                "'completed','duplicate',CURRENT_TIMESTAMP)"
            )
        )
        with pytest.raises(RuntimeError, match="MESSAGE_IDEMPOTENCY_CONFLICT"):
            migrate(connection, "upgrade", "head")
        assert connection.execute(text("SELECT COUNT(*) FROM messages")).scalar_one() == 2
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0001_initial_demo"
        )


def test_initial_downgrade_refuses_to_delete_user_facts():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0001_initial_demo")
        seed(connection)
        with pytest.raises(RuntimeError, match="NONEMPTY_DATABASE"):
            migrate(connection, "downgrade", "base")
        assert connection.execute(text("SELECT content FROM messages")).scalar_one() == "fact"
