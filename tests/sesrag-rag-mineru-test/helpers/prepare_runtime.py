"""每子project独占凭据；模板与真实秘密分离，永不自动读取docs/secret。"""

import base64
import secrets
import shutil

from helpers.common import SUITE, run_path, write


def prepare(identity, project, lane, images, owner, real=None):
    directory = run_path("runtime", identity) / project
    directory.mkdir(parents=True, exist_ok=False)
    directory.chmod(0o700)
    password, token = secrets.token_hex(32), secrets.token_hex(32)
    state_key = base64.b64encode(secrets.token_bytes(32)).decode()
    config_dir = directory / "config"
    config_dir.mkdir()
    for source, target in (
        (f"profiles.{lane if lane == 'local' else 'real.example'}.json", "profiles.json"),
        (f"models.{lane if lane == 'local' else 'real.example'}.json", "models.json"),
    ):
        shutil.copyfile(SUITE / "fixtures" / source, config_dir / target)
    values = {
        "SUITE_DIR": SUITE.as_posix(),
        "RUN_DIR": directory.as_posix(),
        "INPUT_DIR": (run_path("tmp", identity) / "inputs").as_posix(),
        "REPORT_DIR": (run_path("artifacts", identity) / project).as_posix(),
        "TEST_RUN_ID": identity,
        "TEST_OWNER": owner,
        "TEST_PROJECT": project,
        "TEST_PASSWORD": password,
        "TEST_CONTROL_TOKEN": token,
        "APP_IMAGE": images["app"],
        "FRONTEND_IMAGE": images["frontend"],
        "TOOLS_IMAGE": images["tools"],
        "MINERU_ENABLED": "true" if lane == "local" else "false",
        "MINERU_API_KEY": "dummy-mineru-local-only" if lane == "local" else "",
        "MINERU_STATE_ENCRYPTION_KEY": state_key,
        "MINERU_STORAGE_HOST_ALLOWLIST": "storage.mineru.test" if lane == "local" else "",
        "MODEL_API_KEY": "dummy-generation-local-only" if lane == "local" else "",
        "RAG_EMBEDDING_API_KEY": "",
        "RAG_RERANK_API_KEY": "",
        "TEST_LANE": lane,
    }
    if real:
        values.update(real["secrets"])
        for name, source in real["config_paths"].items():
            shutil.copyfile(source, config_dir / name)
        live_dir = run_path("tmp", identity) / "inputs/live"
        live_dir.mkdir(exist_ok=True)
        safe_files = []
        for number, row in enumerate(real["approved_files"]):
            filename = f"{number:02}-{row['filename']}"
            shutil.copyfile(row["source"], live_dir / filename)
            safe_files.append({"file": "/inputs/live/" + filename, "sha256": row["sha256"]})
        write(config_dir / "live-inputs.json", {"files": safe_files, "budget": real["budget"]})
    # env-file只用于插值，子进程环境不继承开发DSN或模型Key。
    for value in values.values():
        if any(c in str(value) for c in "\r\n\x00'"):
            raise ValueError("UNSAFE_ENV_VALUE")
    env_file = directory / "compose.env"
    env_file.write_text("\n".join(f"{k}='{v}'" for k, v in values.items()) + "\n", encoding="utf-8")
    env_file.chmod(0o600)
    private = {
        "database_url": f"postgresql+psycopg://rag_test:{password}@postgres:5432/rag_test",
        "control_token": token,
        "project": project,
        "run_id": identity,
        "owner": owner,
        "lane": lane,
    }
    write(directory / "tools-private.json", private)
    (directory / "tools-private.json").chmod(0o600)
    return directory, values
