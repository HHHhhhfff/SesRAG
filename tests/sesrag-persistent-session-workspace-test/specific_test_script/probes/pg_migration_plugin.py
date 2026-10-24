"""COMP_008～012：把已审查迁移测试的数据库工厂绑定本分类真实PG空专库。"""

import importlib.util
import os
import sys

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url

spec = importlib.util.spec_from_file_location("workspace_db_admin", "/suite/tooling/db-admin.py")
admin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = admin
spec.loader.exec_module(admin)


@pytest.fixture(autouse=True)
def real_postgres_migration(request, monkeypatch):
    if request.node.path.name not in {
        "test_v2_session_migrations.py",
        "test_migration_supplements.py",
    }:
        yield
        return
    run_id = os.environ["WS_TEST_RUN_ID"]
    database = "sesrag_ws_migration_" + run_id[-8:]
    target = admin.validate_target(
        database_url=os.environ["WORKSPACE_TEST_DATABASE_URL"],
        run_id=run_id,
        database=database,
        namespace=os.environ["WORKSPACE_EXPECTED_NAMESPACE"],
        server_id=os.environ["WORKSPACE_EXPECTED_SERVER_ID"],
    )
    admin.execute("create", target)
    url = make_url(os.environ["WORKSPACE_TEST_DATABASE_URL"]).set(database=database)
    engine = create_engine(url)

    # COMP_009的同一冲突在PG需要一个真实存在的另一Thread；
    # 否则夹具在到达迁移预检前就被外键拒绝，不能误报迁移缺陷。
    @event.listens_for(engine, "before_cursor_execute")
    def prepare_other_thread(connection, cursor, statement, parameters, context, executemany):
        if statement == "UPDATE messages SET thread_id='other'":
            cursor.execute(
                "INSERT INTO threads "
                "(thread_id,owner_id,title,next_message_seq,created_at,updated_at) "
                "VALUES ('other','owner','other',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )

    monkeypatch.setattr(request.node.module, "migration_engine", lambda: engine)
    try:
        yield
    finally:
        engine.dispose()
        admin.execute("drop", target)
