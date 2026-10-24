"""TEST-002 只读技术探测；不创建 Thread、Run 或产品验收结果。"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

SUITE = Path(__file__).resolve().parents[1]
API = "http://api:8000"
FRONTEND = "http://frontend:5173"
PROVIDER = "http://provider:8080"
CONTROL = "http://provider:8081"
MAX_HTTP_BYTES = 64 * 1024
TIMEOUT = 5


class ProbeError(RuntimeError):
    """错误码是唯一公开诊断，禁止直接发布驱动、HTTP和文件异常。"""


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        raise ProbeError("ARGUMENTS_INVALID")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, _request, _file, _code, _message, _headers, _new_url):
        raise ProbeError("HTTP_REDIRECT_REJECTED")


def read_http(url, *, token=None, json_body=True):
    headers = {"Accept": "application/json" if json_body else "text/html"}
    if urlsplit(url).netloc == "frontend:5173":
        # Docker DNS用于传输；Host模拟真实回环访问，不关闭Vite的主机名安全校验。
        headers["Host"] = "127.0.0.1:5173"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # 固定容器地址不继承宿主HTTP代理，也不跟随跳转离开测试网络。
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(Request(url, headers=headers), timeout=TIMEOUT) as response:
            if response.status != 200:
                raise ProbeError(f"HTTP_STATUS_{response.status}")
            raw = response.read(MAX_HTTP_BYTES + 1)
    except HTTPError as error:
        raise ProbeError(f"HTTP_STATUS_{error.code}") from None
    if len(raw) > MAX_HTTP_BYTES:
        raise ProbeError("HTTP_RESPONSE_TOO_LARGE")
    if not json_body:
        return raw
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ProbeError("HTTP_JSON_INVALID")
    return payload


def database_kwargs():
    try:
        parsed = urlsplit(os.environ.get("DATABASE_URL", ""))
        valid = (
            parsed.scheme in {"postgres", "postgresql", "postgresql+psycopg", "postgresql+asyncpg"}
            and parsed.hostname == "postgres"
            and parsed.port in {None, 5432}
            and unquote(parsed.path) == "/sesrag_workspace"
            and unquote(parsed.username or "") == "sesrag"
            and bool(parsed.password)
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise ProbeError("DATABASE_TARGET_REJECTED")
    return {
        "host": "postgres",
        "port": 5432,
        "dbname": "sesrag_workspace",
        "user": "sesrag",
        "password": unquote(parsed.password),
        "connect_timeout": TIMEOUT,
        "options": "-c default_transaction_read_only=on -c statement_timeout=5000",
    }


def validate_readiness(payload):
    count = payload.get("worker_count")
    if (
        payload.get("status") != "ok"
        or payload.get("database") != "ready"
        or payload.get("redis") != "ready"
        or payload.get("worker") != "ready"
        or type(count) is not int
        or count < 1
    ):
        raise ProbeError("APPLICATION_NOT_READY")
    return count


def validate_profiles(actual, expected):
    def keyed(rows):
        return {(item["profile_id"], item["version"]): item for item in rows}

    desired = keyed(expected)
    observed = keyed(actual)
    defaults = [item for item in actual if item.get("is_default")]
    if (
        len(actual) != 4
        or len(observed) != len(actual)
        or observed != desired
        or len(defaults) != 1
        or defaults[0]["profile_id"] != "mock-default"
        or defaults[0]["version"] != 1
        or any(item.get("status") != "enabled" for item in actual)
    ):
        raise ProbeError("PROFILE_BASELINE_MISMATCH")
    return {
        "count": len(actual),
        "default_profile": "mock-default@1",
        "profiles": sorted(f"{key[0]}@{key[1]}" for key in observed),
    }


def expected_profiles():
    return json.loads((SUITE / "fixtures/model-profiles.json").read_text(encoding="utf-8"))


def probe_configuration(run_id):
    match = re.fullmatch(r"ws-(\d{8}t\d{6}z)-[0-9a-f]{8}", run_id)
    if match is None:
        raise ProbeError("RUN_ID_REJECTED")
    try:
        datetime.strptime(match.group(1), "%Y%m%dt%H%M%Sz")
    except ValueError:
        raise ProbeError("RUN_ID_REJECTED") from None
    database_kwargs()
    if not os.environ.get("MODEL_API_KEY") or not os.environ.get("PROVIDER_CONTROL_TOKEN"):
        raise ProbeError("CREDENTIAL_INPUT_MISSING")
    redis = urlsplit(os.environ.get("REDIS_URL", ""))
    if (
        redis.scheme != "redis"
        or redis.hostname != "redis"
        or redis.port not in {None, 6379}
        or redis.path not in {"", "/0"}
        or redis.query
        or redis.fragment
        or redis.username
        or redis.password
    ):
        raise ProbeError("REDIS_TARGET_REJECTED")
    return {"credential_inputs_present": True, "database_name": "sesrag_workspace"}


def probe_encoding():
    from backend.infrastructure.providers.context_counter import load_encoding_offline

    encoding = load_encoding_offline("cl100k_base")
    count = len(encoding.encode("WS_OFFLINE_ENCODING_V1 中文 fixture", disallowed_special=()))
    if count < 1:
        raise ProbeError("OFFLINE_ENCODING_INVALID")
    return {
        "encoding_name": "cl100k_base",
        "offline_asset_verified": True,
        "sample_token_count": count,
    }


def probe_database():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from backend.application.model_profiles import validate_profile_config
    from backend.domain.ports.session import ModelProfileRecord

    heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
    if len(heads) != 1:
        raise ProbeError("MIGRATION_HEAD_INVALID")
    expected = expected_profiles()
    for profile in expected:
        validate_profile_config(profile)
    columns = list(ModelProfileRecord.__dataclass_fields__)
    with psycopg.connect(**database_kwargs(), row_factory=dict_row) as connection:
        version = connection.execute("SHOW server_version_num").fetchone()["server_version_num"]
        vector = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        if vector is None or not re.fullmatch(r"[0-9A-Za-z.+-]+", vector["extversion"]):
            raise ProbeError("VECTOR_EXTENSION_MISSING")
        revisions = [
            row["version_num"]
            for row in connection.execute(
                "SELECT version_num FROM alembic_version ORDER BY version_num"
            ).fetchall()
        ]
        if revisions != heads:
            raise ProbeError("MIGRATION_REVISION_MISMATCH")
        profiles = connection.execute(
            sql.SQL("SELECT {} FROM model_profiles ORDER BY profile_id, version").format(
                sql.SQL(", ").join(sql.Identifier(name) for name in columns)
            )
        ).fetchall()
    profiles_summary = validate_profiles(profiles, expected)
    return {
        "server_version_num": int(version),
        "vector_extension": vector["extversion"],
        "alembic_head": heads[0],
        **profiles_summary,
    }


def probe_redis():
    from redis import Redis

    with Redis.from_url(
        os.environ["REDIS_URL"],
        socket_timeout=TIMEOUT,
        socket_connect_timeout=TIMEOUT,
        retry_on_timeout=False,
    ) as client:
        if client.ping() is not True:
            raise ProbeError("REDIS_PING_FAILED")
    return {"ping": "PONG"}


def probe_api():
    from backend.api.schemas.v2.models import ModelListResponse

    if read_http(API + "/health/live") != {"status": "ok"}:
        raise ProbeError("APPLICATION_LIVE_FAILED")
    count = validate_readiness(read_http(API + "/health/ready"))
    payload = ModelListResponse.model_validate(read_http(API + "/api/v2/models")).model_dump()
    expected = expected_profiles()
    observed = {(item["profile_id"], item["version"]): item for item in payload["models"]}
    if len(observed) != 4 or len(payload["models"]) != 4:
        raise ProbeError("PROFILE_AVAILABILITY_MISMATCH")
    fields = (
        "provider_kind",
        "model_name",
        "context_window_tokens",
        "max_output_tokens",
        "status",
        "is_default",
    )
    for profile in expected:
        actual = observed.get((profile["profile_id"], profile["version"]))
        if (
            actual is None
            or actual.get("reason") is not None
            or any(actual[field] != profile[field] for field in fields)
        ):
            raise ProbeError("PROFILE_AVAILABILITY_MISMATCH")
    if payload["default_profile"] != {"profile_id": "mock-default", "version": 1}:
        raise ProbeError("PROFILE_AVAILABILITY_MISMATCH")
    return {
        "live": "ok",
        "database": "ready",
        "redis": "ready",
        "worker_count": count,
        "available_profiles": 4,
    }


def probe_frontend():
    body = read_http(FRONTEND + "/", json_body=False).lower()
    if b"<html" not in body:
        raise ProbeError("FRONTEND_HTML_INVALID")
    if read_http(FRONTEND + "/health/live") != {"status": "ok"}:
        raise ProbeError("FRONTEND_LIVE_FAILED")
    count = validate_readiness(read_http(FRONTEND + "/health/ready"))
    return {"html": "readable", "same_origin_health": "ready", "worker_count": count}


def probe_provider(run_id):
    inference = read_http(PROVIDER + "/health")
    control = read_http(CONTROL + "/health")
    authenticated = read_http(
        CONTROL + "/control/health", token=os.environ["PROVIDER_CONTROL_TOKEN"]
    )
    identity = inference.get("instance_id", "")
    if (
        not isinstance(identity, str)
        or re.fullmatch(re.escape(run_id) + r"-[0-9a-f]{32}", identity) is None
        or inference.get("status") != "ok"
        or control != inference
        or authenticated != inference
    ):
        raise ProbeError("PROVIDER_IDENTITY_MISMATCH")
    return {
        "inference_health": "ok",
        "control_health": "ok",
        "control_auth": "accepted",
        "instance_id": identity,
    }


def probe_environment():
    run_id = os.environ.get("WS_TEST_RUN_ID", "")
    checks = []

    def check(name, operation):
        try:
            checks.append({"id": name, "status": "passed", "details": operation()})
            return True
        except Exception as error:
            checks.append(
                {
                    "id": name,
                    "status": "failed",
                    "code": str(error)
                    if isinstance(error, ProbeError)
                    else f"{name.upper()}_CHECK_FAILED",
                }
            )
            return False

    valid_config = check("configuration", lambda: probe_configuration(run_id))
    if valid_config:
        for name, operation in (
            ("encoding", probe_encoding),
            ("database", probe_database),
            ("redis", probe_redis),
            ("provider", lambda: probe_provider(run_id)),
            ("api", probe_api),
            ("frontend", probe_frontend),
        ):
            check(name, operation)
    return {
        "schema_version": 1,
        "status": "passed" if all(item["status"] == "passed" for item in checks) else "failed",
        "run_id": run_id if valid_config else None,
        "checks": checks,
        "product_acceptance": "not_run",
        "business_facts_created": False,
    }


def main(argv=None):
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--json", action="store_true", help="保持兼容；始终输出安全JSON")
        parser.parse_args(argv)
        result = probe_environment()
    except Exception as error:
        result = {
            "schema_version": 1,
            "status": "failed",
            "code": str(error) if isinstance(error, ProbeError) else "ENVIRONMENT_PROBE_FAILED",
        }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
