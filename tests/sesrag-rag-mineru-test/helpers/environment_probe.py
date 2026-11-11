"""技术就绪检查与少量协议自检；不是产品分类，产品结果始终not_run。"""

import asyncio
import json
import platform
import socket
import subprocess
import time
from importlib.metadata import version
from pathlib import Path

import httpx
from sqlalchemy import text

from backend.config import Settings
from backend.db.session import create_engine
from backend.infrastructure.providers.context_counter import load_encoding_offline


async def main():
    private = json.loads(Path("/run/secrets/tools-private.json").read_text())
    engine = create_engine(Settings())
    try:
        async with engine.connect() as conn:
            revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
            extension = await conn.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            )
            counts = {
                table: await conn.scalar(text(f"SELECT count(*) FROM {table}"))
                for table in ("knowledge_bases", "embedding_profiles", "model_profiles")
            }
        if (
            revision != "0010_rag_task_and_run_protocol"
            or not extension
            or any(not n for n in counts.values())
        ):
            raise ValueError("SCHEMA_OR_PROFILE_NOT_READY")
    finally:
        await engine.dispose()
    # 使用容器内IP作为浏览器/HTTP同源地址，保留Vite的Host防护，不扩白名单。
    frontend_origin = "http://" + socket.gethostbyname("frontend") + ":5173"
    async with httpx.AsyncClient(base_url=frontend_origin, timeout=30, trust_env=False) as client:
        deadline = time.monotonic() + 90
        while True:
            response = await client.get("/health/ready")
            ready = response.json()
            if ready.get("database") == "ready" and ready.get("worker") == "ready":
                break
            if time.monotonic() > deadline:
                raise ValueError("WORKER_NOT_READY")
            await asyncio.sleep(1)
        # 建立一次Mock/off技术流，证明代理能真正传SSE；不计产品用例或业务能力验收。
        response = await client.post(
            "/api/v2/threads", json={"title": "environment transport probe"}
        )
        response.raise_for_status()
        thread = response.json()
        response = await client.post(
            f"/api/v3/threads/{thread['thread_id']}/messages",
            json={
                "branch_id": thread["default_branch_id"],
                "content": "环境传输探针",
                "expected_version": 0,
                "rag": {"enabled": False},
                "model_profile_id": "mock-default",
                "model_profile_version": 1,
            },
            headers={"Idempotency-Key": "environment-transport-probe"},
        )
        response.raise_for_status()
        run = response.json()["run_id"]
        async with client.stream("GET", f"/api/v3/runs/{run}/events/stream") as stream:
            stream.raise_for_status()
            if "text/event-stream" not in stream.headers.get("content-type", ""):
                raise ValueError("SSE_CONTENT_TYPE_INVALID")
            observed = 0
            async for line in stream.aiter_lines():
                if line.startswith("data:"):
                    observed += 1
                    if observed >= 1:
                        break
        if not observed:
            raise ValueError("SSE_NO_EVENT")
    encoding = load_encoding_offline("cl100k_base")
    token_count = len(encoding.encode("离线工具准备 probe"))
    browser = subprocess.run(
        ["node", "/suite/helpers/browser.mjs", frontend_origin],
        capture_output=True,
        text=True,
        timeout=45,
        check=True,
    )
    result = {
        "status": "passed",
        "product": "not_run",
        "schema_revision": revision,
        "pgvector": extension,
        "counts": counts,
        "ready": ready,
        "sse_proxy": "observed_data_event",
        "browser": json.loads(browser.stdout.strip()),
        "python": platform.python_version(),
        "packages": {
            n: version(n)
            for n in (
                "jsonschema",
                "httpx",
                "sqlalchemy",
                "tiktoken",
                "pytest",
                "pytest-asyncio",
                "ruff",
            )
        },
        "offline_tokenizer": {"encoding": "cl100k_base", "sample_tokens": token_count},
        "transport_scope": "local受控，不证明真实DNS/TLS/模型/解析效果",
        "lane": private["lane"],
    }
    Path("/reports/environment.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
