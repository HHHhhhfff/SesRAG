"""本轮用例专属真PG与正式API/Worker夹具；不预写成功事实，不共享可变业务数据。"""

import asyncio
import json
import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from helpers.common import SUITE, load
from helpers.fixture_admin import FixtureAdmin
from sqlalchemy import create_engine as sync_engine
from sqlalchemy import select, text


class CaseEnvironment:
    template = None

    def __init__(self, case, **overrides):
        self.case, self.overrides = case, overrides
        self.admin = FixtureAdmin()
        self.case_key = case.case_id + "_" + uuid4().hex[:12].upper()
        self.name = self.admin.database_name(self.case_key)
        self.url = self.admin.url.set(database=self.name)
        self.directory = Path(tempfile.mkdtemp(prefix=case.case_id + "-", dir="/data/scratch"))
        self.runtime = self.client = None

    @staticmethod
    async def initialize(url, directory):
        from backend.application.rag_profiles import import_profiles
        from backend.config import Settings
        from backend.db.session import create_engine, create_session_factory
        from backend.infrastructure.session.model_profiles import SQLModelProfileRepository
        from backend.tools.upgrade_rag_schema import upgrade

        settings = Settings(
            database_url=url.render_as_string(hide_password=False),
            owner_id="rag-test-owner-a",
            upload_dir=str(directory / "uploads"),
            rag_artifact_dir=str(directory / "artifacts"),
            rag_tmp_dir=str(directory / "tmp"),
            redis_enabled=False,
            _env_file=None,
        )
        await upgrade(settings)
        engine = create_engine(settings)
        try:
            async with create_session_factory(engine)() as session:
                await import_profiles(session, load(SUITE / "fixtures/profiles.local.json"))
                await SQLModelProfileRepository(session).import_profiles(
                    load(SUITE / "fixtures/models.local.json")
                )
                await session.commit()
        finally:
            await engine.dispose()

    def __enter__(self):
        from backend.app import create_app
        from backend.config import Settings
        from backend.workers.runtime import WorkerRuntime

        # 每分类首例真实执行迁移；后续从无业务的专属模板克隆，仍用相同PG约束。
        if CaseEnvironment.template is None:
            key = "TEMPLATE_" + uuid4().hex[:12].upper()
            url = self.admin.create_database(key)
            CaseEnvironment.template = (key, self.admin.database_name(key))
            asyncio.run(self.initialize(url, self.directory))
        engine = sync_engine(self.admin.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as conn:
                conn.execute(text(f'CREATE DATABASE "{self.name}" TEMPLATE "{self.template[1]}"'))
        finally:
            engine.dispose()
        values = dict(
            database_url=self.url.render_as_string(hide_password=False),
            owner_id="rag-test-owner-a",
            redis_enabled=False,
            auto_create_schema=False,
            upload_dir=str(self.directory / "uploads"),
            rag_artifact_dir=str(self.directory / "artifacts"),
            rag_tmp_dir=str(self.directory / "tmp"),
            queue_poll_interval=0.05,
            task_heartbeat_interval=1,
            task_lease_ttl=10,
            _env_file=None,
        )
        values.update(self.overrides)
        self.settings = Settings(**values)
        self.app = create_app(self.settings)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.runtime = WorkerRuntime(
            self.settings, self.app.state.session_factory, self.app.state.notifier
        )
        self.base = self.request("GET", "/api/v3/knowledge-bases")["items"][0]["knowledge_base_id"]
        self.case.note(
            "准备",
            {
                "隔离数据库": "hash派生专属PG",
                "前置": "真实迁移模板+正式Profile导入",
                "业务写入": "正式API及真实Worker",
                "用例": self.case.case_id,
            },
        )
        return self

    def __exit__(self, *_):
        try:
            if self.client:
                self.client.__exit__(None, None, None)
        finally:
            self.admin.drop_database(self.case_key)
            shutil.rmtree(self.directory)

    def call(self, function, *args, **kwargs):
        from functools import partial

        return self.client.portal.call(partial(function, *args, **kwargs))

    def request(self, method, path, expected=(200,), **kwargs):
        response = self.client.request(method, path, **kwargs)
        self.case.check(
            response.status_code in expected,
            method + " " + path + " 状态码",
            {
                "status": response.status_code,
                "code": response.json().get("code")
                if response.headers.get("content-type", "").startswith("application/json")
                and isinstance(response.json(), dict)
                else None,
            },
        )
        return response.json()

    def sql(self, statement, parameters=None):
        async def execute():
            async with self.app.state.session_factory() as session:
                result = await session.execute(text(statement), parameters or {})
                rows = [dict(r) for r in result.mappings()] if result.returns_rows else []
                await session.commit()
                return rows

        return self.call(execute)

    def import_profiles(self, entries):
        from backend.application.rag_profiles import import_profiles

        async def execute():
            async with self.app.state.session_factory() as session:
                await import_profiles(session, entries)
                await session.commit()

        return self.call(execute)

    def step(self, advance_wait=True, runtime=None):
        async def advance():
            from backend.db.models import TaskModel, utc_now

            async with self.app.state.session_factory() as session:
                rows = (
                    await session.scalars(
                        select(TaskModel).where(
                            TaskModel.state.in_(("waiting_external", "retry_waiting"))
                        )
                    )
                ).all()
                for row in rows:
                    row.available_at = utc_now() - timedelta(seconds=1)
                await session.commit()

        if advance_wait:
            self.call(advance)
        return self.call((runtime or self.runtime).run_once)

    def finish(self, path, field="state", steps=40, successful=True):
        for _ in range(steps):
            row = self.request("GET", path)
            if row[field] in {"succeeded", "failed", "cancelled"}:
                if successful:
                    self.case.equal(row[field], "succeeded", "正式任务完整成功")
                return row
            self.step()
        raise AssertionError("有界Worker步骤内未获得终态：" + path)

    def upload(
        self,
        raw=b"ALPHA code is 37.\n",
        filename="knowledge.txt",
        parse=None,
        base=None,
        tags=None,
        key=None,
        expected=(202,),
        finish=True,
        mime=None,
    ):
        office = Path(filename).suffix.lower() not in {".txt", ".md"}
        if parse is None:
            parse = (
                {"cloud_consent": True, "consent_version": "mineru-office-outbound-v1"}
                if office
                else {}
            )
        response = self.request(
            "POST",
            "/api/v3/documents",
            expected=expected,
            data={
                "knowledge_base_id": base or self.base,
                "parse": json.dumps(parse),
                "tags": json.dumps(tags or []),
            },
            files={"file": (filename, raw, mime or "application/octet-stream")},
            headers={"Idempotency-Key": key if key is not None else str(uuid4())},
        )
        if finish and "document_id" in response:
            self.finish("/api/v3/index-builds/" + response["latest_build"]["index_batch_id"])
            response = self.request("GET", "/api/v3/documents/" + response["document_id"])
        return response

    def diagnostic(self, *, query="ALPHA", finish=True, **kwargs):
        response = self.request(
            "POST",
            "/api/v3/retrieval-executions",
            expected=(202,),
            json={"query": query, "knowledge_base_id": self.base, **kwargs},
            headers={"Idempotency-Key": str(uuid4())},
        )
        return (
            self.finish("/api/v3/retrieval-executions/" + response["execution_id"])
            if finish
            else response
        )

    def run(self, *, content="What is ALPHA?", enabled=True, finish=True, **kwargs):
        thread = self.request(
            "POST", "/api/v2/threads", expected=(201,), json={"title": self.case.case_id}
        )
        payload = {
            "branch_id": thread["default_branch_id"],
            "expected_version": 0,
            "content": content,
            "rag": {"enabled": enabled, **({"knowledge_base_id": self.base} if enabled else {})},
            **kwargs,
        }
        created = self.request(
            "POST",
            f"/api/v3/threads/{thread['thread_id']}/messages",
            expected=(201,),
            json=payload,
            headers={"Idempotency-Key": str(uuid4())},
        )
        return self.finish("/api/v3/runs/" + created["run_id"], "status") if finish else created

    def plan(self, scope, kind, actions):
        with httpx.Client(
            base_url="http://scenario-control:8081", trust_env=False, timeout=10
        ) as client:
            response = client.put(
                f"/plans/{scope}/{kind}",
                json=actions,
                headers={"Authorization": "Bearer " + os.environ["TEST_CONTROL_TOKEN"]},
            )
            response.raise_for_status()

    def to_stage(self, build, stage, steps=30):
        identity = build.get("index_batch_id") or build["latest_build"]["index_batch_id"]
        for _ in range(steps):
            row = self.request("GET", "/api/v3/index-builds/" + identity)
            if row["stage"] == stage:
                return row
            self.case.check(
                row["state"] not in {"failed", "cancelled", "succeeded"},
                "进入目标阶段前未异常终止",
                row["error_code"],
            )
            self.step()
        raise AssertionError("未到达阶段：" + stage)

    def next_scope(self, task_id):
        return (
            task_id
            + ":"
            + str(
                self.sql("SELECT generation FROM tasks WHERE task_id=:id", {"id": task_id})[0][
                    "generation"
                ]
                + 1
            )
        )

    def observations(self, scope):
        with httpx.Client(
            base_url="http://scenario-control:8081", trust_env=False, timeout=10
        ) as client:
            return client.get(
                f"/observations/{scope}",
                headers={"Authorization": "Bearer " + os.environ["TEST_CONTROL_TOKEN"]},
            ).json()["calls"]


def cleanup_template():
    if CaseEnvironment.template:
        FixtureAdmin().drop_database(CaseEnvironment.template[0])
        CaseEnvironment.template = None
