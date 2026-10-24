"""TEST-002 环境工具自测；不启动 Docker，也不创建产品业务事实。"""

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
from docx import Document

TOOLING = Path(__file__).resolve().parent
RUN_ID = "ws-20261021t010203z-a1b2c3d4"
NAMESPACE = "sesrag-ws-a1b2c3d4-env"
SERVER_ID = "1234567890123456789"
DATABASE = "sesrag_session_probe_a1b2c3d4"
DSN = "postgresql+asyncpg://sesrag:fake-password@postgres:5432/sesrag_workspace"


def load_tool(name):
    path = TOOLING / f"{name}.py"
    assert path.is_file(), f"尚未实现环境工具 {name}"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_contract_format_dependencies_reject_invalid_timestamp():
    # QLT_002依赖自检：缺少format extras时JSON Schema会静默放过非法时间。
    from jsonschema import Draft202012Validator, FormatChecker

    validator = Draft202012Validator(
        {"type": "string", "format": "date-time"}, format_checker=FormatChecker()
    )
    assert validator.is_valid("2026-10-22T00:00:00Z")
    assert not validator.is_valid("invalid-date-time")


def test_provider_observation_capacity_is_explicit_and_bounded():
    # PERF_002/UI长历史会超过100条；容量可显式到2000，但不能无界积累。
    spec = importlib.util.spec_from_file_location(
        "ws_provider_capacity", TOOLING.parent / "fixtures/provider/server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.observation_limit("100") == 100
    assert module.observation_limit("2000") == 2000
    for value in ["0", "2001", "-1", "bad"]:
        with pytest.raises(ValueError):
            module.observation_limit(value)


def test_quality_contract_negative_uses_only_repository_registry(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "ws_quality_probe", TOOLING.parent / "specific_test_script/probes/quality-probe.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import urllib.request

    def deny_network(*args, **kwargs):
        raise AssertionError("契约负例不得查询网络")

    monkeypatch.setattr(urllib.request, "urlopen", deny_network)
    assert module.invalid_contract_errors(TOOLING.parents[2] / "contracts")


def test_provider_selftest_rejects_multiple_frames_without_interframe_wait(monkeypatch):
    provider_test = load_tool("provider-selftest")

    class BufferedResponse(io.BytesIO):
        status = 200
        headers = {"Content-Type": "text/event-stream"}

    stream = b'data: {"chunk":1}\n\ndata: {"chunk":2}\n\ndata: {"chunk":3}\n\ndata: [DONE]\n\n'
    monkeypatch.setattr(
        provider_test, "urlopen", lambda *_args, **_kwargs: BufferedResponse(stream)
    )
    with pytest.raises(provider_test.SelfTestFailure, match="inter-frame waits"):
        provider_test.request_slow_sse(provider_test.completion_payload())


@pytest.mark.parametrize(
    "override,code",
    [
        (
            {"database_url": "postgresql://sesrag:fake@127.0.0.1/sesrag_workspace"},
            "DATABASE_TARGET_REJECTED",
        ),
        (
            {"database_url": "postgresql://sesrag:fake@postgres/development"},
            "DATABASE_TARGET_REJECTED",
        ),
        ({"database_url": DSN + "?host=development"}, "DATABASE_TARGET_REJECTED"),
        ({"database": "sesrag_workspace"}, "DATABASE_NAME_REJECTED"),
        ({"database": "sesrag_session_probe_deadbeef"}, "DATABASE_NAME_REJECTED"),
        ({"database": 'sesrag_session_probe_a1b2c3d4"; DROP DATABASE x'}, "DATABASE_NAME_REJECTED"),
        ({"run_id": "ws-20260230t010203z-a1b2c3d4"}, "RUN_ID_REJECTED"),
        ({"namespace": "sesrag-ws-deadbeef-env"}, "NAMESPACE_REJECTED"),
        ({"namespace": "sesrag-ws-a1b2c3d4-security"}, "NAMESPACE_REJECTED"),
        ({"server_id": ""}, "SERVER_ID_REJECTED"),
    ],
)
def test_database_guard_rejects_unsafe_targets_before_connection(override, code):
    db = load_tool("db-admin")
    kwargs = dict(
        database_url=DSN, run_id=RUN_ID, database=DATABASE, namespace=NAMESPACE, server_id=SERVER_ID
    )
    kwargs.update(override)
    with pytest.raises(db.ToolError, match=code):
        db.validate_target(**kwargs)


def test_database_guard_accepts_only_the_current_owned_database():
    db = load_tool("db-admin")
    target = db.validate_target(
        database_url=DSN, run_id=RUN_ID, database=DATABASE, namespace=NAMESPACE, server_id=SERVER_ID
    )
    assert target.database == "sesrag_session_probe_a1b2c3d4"
    assert target.connection_kwargs["host"] == "postgres"
    assert target.connection_kwargs["dbname"] == "postgres"
    assert target.namespace == "sesrag-ws-a1b2c3d4-env"


def test_database_guard_accepts_the_registered_quality_category():
    db = load_tool("db-admin")
    target = db.validate_target(
        database_url=DSN,
        run_id=RUN_ID,
        database=DATABASE,
        namespace="sesrag-ws-a1b2c3d4-quality",
        server_id=SERVER_ID,
    )
    assert target.namespace == "sesrag-ws-a1b2c3d4-quality"


def test_database_cli_rejects_bad_target_without_opening_connection(monkeypatch, capsys):
    db = load_tool("db-admin")
    monkeypatch.setenv("WS_TEST_RUN_ID", RUN_ID)
    monkeypatch.setenv("DATABASE_URL", "postgresql://sesrag:PRIVATE_SENTINEL@localhost/production")

    def unexpected_connection(**_kwargs):
        pytest.fail("非法目标不应建立数据库连接")

    monkeypatch.setattr(db.psycopg, "connect", unexpected_connection)
    result = db.main(
        [
            "drop",
            "--database",
            DATABASE,
            "--expected-server-id",
            SERVER_ID,
            "--expected-namespace",
            NAMESPACE,
        ]
    )
    output = capsys.readouterr()
    assert result == 2
    assert json.loads(output.out)["code"] == "DATABASE_TARGET_REJECTED"
    assert "PRIVATE_SENTINEL" not in output.out + output.err
    assert output.err == ""


def test_database_operation_rejects_unknown_action_before_connection(monkeypatch):
    db = load_tool("db-admin")
    target = db.validate_target(
        database_url=DSN, run_id=RUN_ID, database=DATABASE, namespace=NAMESPACE, server_id=SERVER_ID
    )

    def unexpected_connection(**_kwargs):
        pytest.fail("未知操作不应建立数据库连接或回落到专库自检")

    monkeypatch.setattr(db.psycopg, "connect", unexpected_connection)
    with pytest.raises(db.ToolError, match="ARGUMENTS_INVALID"):
        db.execute("unknown", target)


@pytest.mark.parametrize(
    "actual_server,actual_namespace",
    [("9876543210123456789", NAMESPACE), (SERVER_ID, "development")],
)
def test_database_guard_rejects_server_identity_mismatch(actual_server, actual_namespace):
    db = load_tool("db-admin")
    target = db.validate_target(
        database_url=DSN, run_id=RUN_ID, database=DATABASE, namespace=NAMESPACE, server_id=SERVER_ID
    )
    with pytest.raises(db.ToolError, match="SERVER_IDENTITY_MISMATCH"):
        db.verify_server_identity(target, actual_server, actual_namespace)


def test_database_guard_refuses_nonempty_probe_and_unowned_databases():
    db = load_tool("db-admin")
    target = db.validate_target(
        database_url=DSN, run_id=RUN_ID, database=DATABASE, namespace=NAMESPACE, server_id=SERVER_ID
    )
    marker = db.ownership_marker(target)
    with pytest.raises(db.ToolError, match="DATABASE_NOT_EMPTY"):
        db.validate_database_state(
            target, {"owner": "sesrag", "marker": marker, "object_count": 1}, require_empty=True
        )
    with pytest.raises(db.ToolError, match="DATABASE_OWNERSHIP_MISMATCH"):
        db.validate_database_state(
            target, {"owner": "sesrag", "marker": None, "object_count": 0}, require_empty=True
        )


@pytest.mark.parametrize("worker_count", [0, None, "1", True])
def test_readiness_does_not_treat_http_200_as_worker_readiness(worker_count):
    probe = load_tool("environment_probe")
    payload = {
        "status": "ok",
        "database": "ready",
        "redis": "ready",
        "worker": "ready",
        "worker_count": worker_count,
    }
    with pytest.raises(probe.ProbeError, match="APPLICATION_NOT_READY"):
        probe.validate_readiness(payload)


def test_readiness_accepts_a_ready_worker():
    probe = load_tool("environment_probe")
    assert (
        probe.validate_readiness(
            {
                "status": "ok",
                "database": "ready",
                "redis": "ready",
                "worker": "ready",
                "worker_count": 1,
            }
        )
        == 1
    )


def test_frontend_probe_uses_loopback_host_without_disabling_host_validation(monkeypatch):
    probe = load_tool("environment_probe")
    seen = []

    class Response(io.BytesIO):
        status = 200

    class Opener:
        def open(self, request, timeout):
            seen.append((request.full_url, request.get_header("Host")))
            assert request.get_header("Host") == "127.0.0.1:5173"
            return Response(b"<html></html>")

    monkeypatch.setattr(probe, "build_opener", lambda *_args: Opener())
    assert probe.read_http(probe.FRONTEND + "/", json_body=False) == b"<html></html>"
    assert seen == [("http://frontend:5173/", "127.0.0.1:5173")]


def test_profile_baseline_rejects_mutated_budget_and_duplicate_default():
    probe = load_tool("environment_probe")
    expected = json.loads(
        (TOOLING.parent / "fixtures/model-profiles.json").read_text(encoding="utf-8")
    )
    actual = json.loads(json.dumps(expected))
    actual[2]["max_output_tokens"] = 256
    with pytest.raises(probe.ProbeError, match="PROFILE_BASELINE_MISMATCH"):
        probe.validate_profiles(actual, expected)
    actual = json.loads(json.dumps(expected))
    actual[2]["is_default"] = True
    with pytest.raises(probe.ProbeError, match="PROFILE_BASELINE_MISMATCH"):
        probe.validate_profiles(actual, expected)


def test_fixture_generator_writes_reproducible_docx_and_safe_manifest(tmp_path):
    prepare = load_tool("prepare-fixtures")
    first = prepare.prepare_fixtures(tmp_path / "first")
    second = prepare.prepare_fixtures(tmp_path / "second")
    assert first == second
    assert first["schema_version"] == 1
    assert first["fixture_version"] == "workspace-fixtures-v1"
    names = {item["name"] for item in first["files"]}
    assert names == {"history-long.txt", "markdown-xss.md", "minimal.docx"}
    for item in first["files"]:
        assert item["bytes"] > 0 and item["token_count"] > 0
        assert len(item["sha256"]) == 64
        assert not Path(item["name"]).is_absolute()
        assert (tmp_path / "first" / item["name"]).read_bytes() == (
            tmp_path / "second" / item["name"]
        ).read_bytes()
    with zipfile.ZipFile(tmp_path / "first/minimal.docx") as document:
        assert document.testzip() is None
        assert "word/document.xml" in document.namelist()
    assert Document(tmp_path / "first/minimal.docx").paragraphs[0].text == "WS_DOCX_SYNTHETIC_V1"
    assert (
        next(item for item in first["files"] if item["name"] == "history-long.txt")["token_count"]
        > 8192
    )
    assert "<script>" in (tmp_path / "first/markdown-xss.md").read_text(encoding="utf-8")
    assert str(tmp_path) not in json.dumps(first)


def test_fixture_generator_missing_offline_cache_fails_without_network_or_output(
    monkeypatch, tmp_path, capsys
):
    prepare = load_tool("prepare-fixtures")
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path / "missing-cache"))
    output = tmp_path / "outputs"
    result = prepare.main(["--output", str(output)])
    captured = capsys.readouterr()
    assert result == 2
    assert json.loads(captured.out)["code"] == "FIXTURE_PREPARATION_FAILED"
    assert not output.exists()
    assert str(tmp_path) not in captured.out + captured.err


def test_fixture_generator_refuses_filesystem_root():
    prepare = load_tool("prepare-fixtures")
    with pytest.raises(prepare.FixtureError, match="OUTPUT_PATH_REJECTED"):
        prepare.checked_output(Path(TOOLING.anchor))


def test_fixture_generator_refuses_symlink_output(tmp_path):
    prepare = load_tool("prepare-fixtures")
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("当前宿主不允许创建符号链接")
    with pytest.raises(prepare.FixtureError, match="OUTPUT_PATH_REJECTED"):
        prepare.prepare_fixtures(link)
