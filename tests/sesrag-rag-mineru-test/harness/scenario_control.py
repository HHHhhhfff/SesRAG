"""local专用持久控制面：只保存计划/计数/屏障，绝不更新产品数据库。"""

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

app = FastAPI(docs_url=None, redoc_url=None)
DB = Path(os.environ.get("TEST_CONTROL_DB", "/data/control/control.sqlite"))
KINDS = {
    "mineru_submit",
    "mineru_put",
    "mineru_poll",
    "mineru_download",
    "embedding",
    "rerank",
    "before_publish",
    "generation",
    "model_request",
}


@contextmanager
def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=5)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def auth(value):
    expected = os.environ.get("TEST_CONTROL_TOKEN", "")
    if not expected or value != f"Bearer {expected}":
        raise HTTPException(403, "CONTROL_AUTH_REQUIRED")


def key_valid(scope):
    if not re.fullmatch(r"[a-zA-Z0-9_:-]{1,160}", scope):
        raise HTTPException(422, "INVALID_SCOPE")


def get(key, default=None):
    with connection() as db:
        row = db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def put(key, value):
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, json.dumps(value)))


def next_action(scope, kind, payload):
    # 原子递增跨Worker可见，重启控制面也不丢进度；只持久hash，不保存请求/凭据。
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        key = f"calls:{scope}:{kind}"
        row = db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        number = int(row[0]) if row else 0
        row = db.execute(
            "SELECT value FROM state WHERE key=?", (f"plan:{scope}:{kind}",)
        ).fetchone()
        plan = json.loads(row[0]) if row else []
        if number > 10000:
            raise HTTPException(409, "CONTROL_CALL_LIMIT")
        db.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, str(number + 1)))
        observation = {
            "request_hash": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest(),
            "call": number + 1,
        }
        if kind == "model_request":
            observation["messages"] = payload.get("messages", [])
        db.execute(
            "INSERT OR REPLACE INTO state VALUES (?,?)",
            (
                f"last:{scope}:{kind}",
                json.dumps(observation),
            ),
        )
    return plan[min(number, len(plan) - 1)] if plan else {}


@app.get("/health")
def health():
    return {"status": "ok", "lane": "local", "store": "sqlite", "product_writes": False}


@app.put("/plans/{scope}/{kind}")
async def set_plan(scope: str, kind: str, request: Request, authorization: str = Header("")):
    auth(authorization)
    key_valid(scope)
    if kind not in KINDS:
        raise HTTPException(422, "UNKNOWN_KIND")
    raw = await request.body()
    if len(raw) > 65536:
        raise HTTPException(413, "PLAN_LIMIT")
    value = json.loads(raw)
    if not isinstance(value, list) or not 1 <= len(value) <= 100:
        raise HTTPException(422, "INVALID_PLAN")
    for action in value:
        if not isinstance(action, dict) or set(action) - {
            "status",
            "delay_seconds",
            "fault",
            "state",
            "barrier",
            "response_json",
            "package",
        }:
            raise HTTPException(422, "INVALID_ACTION")
        if not 0 <= action.get("delay_seconds", 0) <= 120:
            raise HTTPException(422, "INVALID_DELAY")
        if action.get("fault") not in {
            None,
            "connection",
            "empty",
            "bad_vector",
            "bad_index",
            "disconnect",
        }:
            raise HTTPException(422, "INVALID_FAULT")
        if action.get("package") not in {None, "safe", "escape", "empty", "html", "nested"}:
            raise HTTPException(422, "INVALID_PACKAGE")
        if action.get("barrier"):
            key_valid(action["barrier"])
    put(f"plan:{scope}:{kind}", value)
    put(f"calls:{scope}:{kind}", 0)
    return {"configured": True}


@app.get("/observations/{scope}")
def observations(scope: str, authorization: str = Header("")):
    auth(authorization)
    key_valid(scope)
    result = {}
    for kind in KINDS:
        result[kind] = {
            "count": get(f"calls:{scope}:{kind}", 0),
            "last": get(f"last:{scope}:{kind}"),
        }
    return {"scope": scope, "calls": result}


@app.put("/barriers/{name}/release")
def release(name: str, authorization: str = Header("")):
    auth(authorization)
    key_valid(name)
    put(f"barrier:{name}", True)
    return {"released": True}


@app.post("/step/{scope}/{kind}")
async def step(scope: str, kind: str, request: Request, authorization: str = Header("")):
    auth(authorization)
    key_valid(scope)
    if kind not in KINDS:
        raise HTTPException(422, "UNKNOWN_KIND")
    raw = await request.body()
    if len(raw) > 1024**2:
        raise HTTPException(413, "REQUEST_LIMIT")
    payload = json.loads(raw)
    action = next_action(scope, kind, payload)
    if action.get("barrier"):
        deadline = time.monotonic() + 120
        while not get(f"barrier:{action['barrier']}", False):
            if time.monotonic() > deadline:
                raise HTTPException(408, "BARRIER_TIMEOUT")
            await asyncio.sleep(0.1)
    await asyncio.sleep(action.get("delay_seconds", 0))
    if kind == "mineru_submit":
        put(
            f"remote:{payload['data_id']}",
            {"filename": payload["filename"], "data_id": payload["data_id"], "uploaded": False},
        )
    if kind == "mineru_put":
        remote = get(f"remote:{scope}")
        if remote:
            remote["uploaded"] = True
            put(f"remote:{scope}", remote)
    return {"action": action, "remote": get(f"remote:{scope}")}


@app.post("/v1/chat/completions")
async def generation(request: Request, authorization: str = Header("")):
    if authorization != "Bearer dummy-generation-local-only":
        raise HTTPException(403, "DUMMY_KEY_REQUIRED")
    raw = await request.body()
    if len(raw) > 1024**2:
        raise HTTPException(413, "GENERATION_INPUT_LIMIT")
    value = json.loads(raw)
    # 合成模型名由case专属Profile选择，支持并发Run隔离，不依赖调用顺序。
    scope = "gen:" + value.get("model", "local-synthetic")
    key_valid(scope)
    selected = scope if get(f"plan:{scope}:generation") is not None else "generation"
    action = next_action(selected, "generation", value)
    if action.get("status", 200) != 200:
        raise HTTPException(action["status"], "SYNTHETIC_PROVIDER_FAILURE")

    async def stream():
        for part in ("合成测试响应：", "业务工具已接入。"):
            await asyncio.sleep(action.get("delay_seconds", 0))
            yield "data: " + json.dumps({"choices": [{"delta": {"content": part}}]}) + "\n\n"
            if action.get("fault") == "disconnect":
                return
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
