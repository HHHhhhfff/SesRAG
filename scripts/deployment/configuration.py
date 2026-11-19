"""凭据只从授权本地文件读取，不进入命令参数、公开报告或镜像。"""

import base64
import json
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "docker/monitoring"))

RUNTIME = ROOT / "scripts/runtime"


def parse_env(path):
    values = {}
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in values:
            raise ValueError("DEPLOY_ENV_FORMAT: 配置格式或重复键无效")
        value = value.strip()
        if value.startswith(("'", '"')) and value[-1:] == value[0]:
            value = value[1:-1]
        values[key] = value
    return values


def write_env(path, values):
    # 单引号保护$和#，拒绝多行/引号，避免dotenv和Compose解释分歧。
    if any(any(c in str(v) for c in "\r\n'") for v in values.values()):
        raise ValueError("DEPLOY_ENV_VALUE: 不支持的dotenv特殊字符")
    Path(path).write_text(
        "# 本机真实运行配置，含Secret，禁止提交或回显。\n"
        + "".join(f"{k}='{v}'\n" for k, v in values.items()),
        encoding="utf-8",
    )


def parse_prepared_secrets(body):
    result = {}
    for title, role in [
        ("会话模型", "chat"),
        ("向量化模型", "embedding"),
        ("重排模型", "rerank"),
        ("MinerU工具", "mineru"),
    ]:
        section = next(
            (
                s
                for s in body.split("```")
                if title in s and re.search(r"(?:key|密钥)\s*[:：]", s, re.I)
            ),
            None,
        )
        if section is None:
            raise ValueError("DEPLOY_SECRET_SECTION: 缺少" + title)

        def field(pattern, section=section):
            match = re.search(pattern + r"\s*[:：]\s*([^\r\n]+)", section, re.I)
            return match.group(1).strip().strip("`") if match else None

        result[role] = {
            "secret": field(r"(?:API[ _-]*)?(?:key|密钥)"),
            "model": field("模型名字"),
            "base_url": field(r"模型基地址(?:\([^\r\n]*?\))?"),
        }
        if not result[role]["secret"]:
            raise ValueError("DEPLOY_SECRET_MISSING: " + role)
    return result


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def runtime_defaults(values):
    # .env.example存在显式空值；缺失和空白都必须落实可用默认。
    defaults = {
        "MINERU_STORAGE_HOST_ALLOWLIST": (
            "mineru.oss-cn-shanghai.aliyuncs.com,cdn-mineru.openxlab.org.cn"
        ),
        "SESRAG_API_PORT": "8000",
        "SESRAG_FRONTEND_PORT": "5173",
    }
    for key, value in defaults.items():
        if not values.get(key):
            values[key] = value


def prepare_configuration(owner):
    from helpers.lifecycle import private_directory

    private_directory(RUNTIME)
    env_path = ROOT / ".env"
    values = parse_env(env_path if env_path.exists() else ROOT / ".env.example")
    old = env_path.read_bytes() if env_path.exists() else None
    source = parse_prepared_secrets(
        (ROOT / "docs/secret/准备的配置信息.md").read_text(encoding="utf-8-sig")
    )
    password = values.get("POSTGRES_PASSWORD", "")
    if not password or "<" in password:
        password = secrets.token_hex(32)
        values["POSTGRES_PASSWORD"] = password
        values["DATABASE_URL"] = f"postgresql+psycopg://sesrag:{password}@postgres:5432/sesrag"
    values.update(
        MOCK_PROVIDER="false",
        MODEL_BASE_URL=source["chat"]["base_url"],
        MODEL_API_KEY=source["chat"]["secret"],
        MODEL_NAME=source["chat"]["model"],
        EMBEDDING_MODEL_NAME=source["embedding"]["model"],
        RAG_EMBEDDING_API_KEY=source["embedding"]["secret"],
        RAG_RERANK_API_KEY=source["rerank"]["secret"],
        MINERU_ENABLED="true",
        MINERU_API_KEY=source["mineru"]["secret"],
        OBS_ENVIRONMENT_ID="live",
        OBS_ENVIRONMENT="live",
        RAG_BOOTSTRAP_CONFIG="/app/config/live-bootstrap.json",
        SESRAG_DEPLOYMENT_OWNER=owner,
    )
    values.setdefault(
        "MINERU_STATE_ENCRYPTION_KEY", base64.b64encode(secrets.token_bytes(32)).decode()
    )
    if not values["MINERU_STATE_ENCRYPTION_KEY"]:
        values["MINERU_STATE_ENCRYPTION_KEY"] = base64.b64encode(secrets.token_bytes(32)).decode()
    runtime_defaults(values)
    if old is not None and not (RUNTIME / "original.env").exists():
        (RUNTIME / "original.env").write_bytes(old)
    # 根.env同样收紧ACL；只处理该文件，不改变仓库目录权限。
    write_env(env_path, values)
    if sys.platform == "win32":
        import csv
        import io
        import subprocess

        sid = next(
            csv.reader(
                io.StringIO(
                    subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True)
                )
            )
        )[1]
        subprocess.run(
            ["icacls", str(env_path), "/inheritance:r", "/grant:r", f"*{sid}:F", "*S-1-5-18:F"],
            check=True,
            capture_output=True,
            timeout=30,
        )
    else:
        env_path.chmod(0o600)
    model = json.loads((ROOT / "docker/model-profiles.example.json").read_text(encoding="utf-8"))[0]
    model.update(
        profile_id="live-chat",
        version=1,
        display_name="真实模型（本机持久部署）",
        provider_kind="openai_compatible",
        model_name=source["chat"]["model"],
        base_url=source["chat"]["base_url"],
        context_window_tokens=8192,
        max_output_tokens=512,
        config_ref="env:MODEL_API_KEY",
        tokenizer_kind="tiktoken",
        tokenizer_version="local-conservative-1",
    )
    model["tokenizer_config"] = {
        "encoding_name": "cl100k_base",
        "message_overhead_tokens": 32,
        "request_overhead_tokens": 128,
        "calibration_version": "local-conservative-not-provider-certified",
        "safety_margin_tokens": 1024,
        "summary_max_tokens": 512,
    }
    write_json(RUNTIME / "model-profiles.json", [model])
    profiles = json.loads((ROOT / "docker/rag-profiles.example.json").read_text(encoding="utf-8"))
    for p in profiles:
        if p["kind"] in ("embedding", "rerank", "retrieval") and "mock" in json.dumps(p):
            p["enabled"] = False
        if p["profile_id"] == "bailian-embedding":
            p["config"]["base_url"] = source["embedding"]["base_url"]
        # 不将真实调用成功伪称计数器已验证；既有安全门槛保持。
    write_json(RUNTIME / "rag-profiles.json", profiles)
    write_json(
        RUNTIME / "bootstrap.json",
        {
            "profiles": profiles,
            "default_embedding": {"profile_id": "bailian-embedding", "version": 1},
        },
    )
    return values
