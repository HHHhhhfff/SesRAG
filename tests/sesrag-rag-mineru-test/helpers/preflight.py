"""无付费预检；真实门禁不足时阻止任何部署后的业务外发。"""

import re
import shutil
from pathlib import Path

from helpers.common import ROOT, SUITE, command, digest, load


def source_fingerprint():
    _, output = command(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        output_limit=10 * 1024**2,
    )
    files = {}
    build = {}
    for name in sorted(set(output.split("\0")) - {""}):
        path = ROOT / name
        if not path.is_file():
            files[name] = "deleted"
            continue
        value = digest(path.read_bytes())
        files[name] = value
        if path.suffix.lower() not in {".md", ".png", ".jpg", ".pdf"} and (
            name.startswith(
                (
                    "backend/",
                    "frontend/",
                    "contracts/",
                    "migrations/",
                    "docker/",
                    "tests/sesrag-rag-mineru-test/",
                )
            )
            or name in {"pyproject.toml", ".dockerignore", "alembic.ini"}
        ):
            build[name] = value
    return {
        "source": digest(files),
        "build_source": digest(build),
        "head": command(["git", "rev-parse", "HEAD"])[1].strip(),
        "dirty": bool(command(["git", "status", "--porcelain"])[1].strip()),
        "files": files,
    }


def check_tools():
    for executable in ("docker", "git"):
        if shutil.which(executable) is None:
            raise ValueError(f"TOOL_MISSING_{executable}")
    version = command(["docker", "compose", "version", "--short"])[1].strip().lstrip("v")
    numbers = tuple(int(n) for n in re.findall(r"\d+", version)[:3])
    if numbers < (2, 24, 4):
        raise ValueError("COMPOSE_2_24_4_REQUIRED")
    info = load_json_command(["docker", "info", "--format", "{{json .}}"])
    if info["OSType"] != "linux":
        raise ValueError("LINUX_CONTAINERS_REQUIRED")
    free = shutil.disk_usage(SUITE).free
    if free < 5 * 1024**3:
        raise ValueError("DISK_BELOW_5_GIB")
    return {
        "compose": version,
        "engine": info["ServerVersion"],
        "os_type": info["OSType"],
        "cpus": info["NCPU"],
        "memory_bytes": info["MemTotal"],
        "disk_free_bytes": free,
        "resource_recommendation": "建议4核/8GiB/20GiB；本检查不证明性能达标",
    }


def load_json_command(args):
    import json

    return json.loads(command(args)[1])


def real_gate(path, plan_name):
    base = (SUITE / "runtime-inputs").resolve()
    candidate = Path(path).resolve()
    if not candidate.is_relative_to(base) or candidate.suffix != ".json" or not candidate.is_file():
        raise ValueError("LIVE_PLAN_OUTSIDE_PRIVATE_INPUTS")
    plan = load(candidate)
    reasons = []
    approved_files = []
    if plan.get("schema_version") != 1 or plan.get("plan") != plan_name:
        reasons.append("LIVE_PLAN_IDENTITY")
    if (
        plan.get("authorized") is not True
        or plan.get("consent_version") != "mineru-office-outbound-v1"
    ):
        reasons.append("OUTBOUND_AUTHORIZATION_REQUIRED")
    for row in plan.get("files", []):
        target = (base / row["file"]).resolve()
        if (
            not target.is_relative_to(base)
            or not target.is_file()
            or digest(target.read_bytes()) != row.get("sha256")
        ):
            reasons.append("LIVE_FILE_HASH_INVALID")
        if "local-only" in target.parts:
            reasons.append("UNSAFE_LIVE_FIXTURE")
        if target.is_file() and target.is_relative_to(base):
            if not 0 < target.stat().st_size <= 10 * 1024**2 or target.suffix.lower() not in {
                ".txt",
                ".md",
                ".doc",
                ".docx",
                ".pdf",
                ".xls",
                ".xlsx",
                ".ppt",
                ".pptx",
            }:
                reasons.append("LIVE_FILE_FORMAT_OR_SIZE_INVALID")
            approved_files.append(
                {"source": target, "sha256": row.get("sha256"), "filename": target.name}
            )
    if not plan.get("files"):
        reasons.append("LIVE_FILES_REQUIRED")
    config_paths = {}
    for name in ("profiles.json", "models.json"):
        target = (base / plan.get("config_files", {}).get(name, "missing")).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            reasons.append("REAL_CONFIG_MISSING_" + name)
        else:
            config_paths[name] = target
    private = (base / plan.get("secret_file", "missing")).resolve()
    secrets = load(private) if private.is_relative_to(base) and private.is_file() else {}
    allowed = {
        "MINERU_ENABLED",
        "MINERU_API_KEY",
        "MINERU_STATE_ENCRYPTION_KEY",
        "MINERU_STORAGE_HOST_ALLOWLIST",
        "RAG_EMBEDDING_API_KEY",
        "RAG_RERANK_API_KEY",
        "MODEL_API_KEY",
    }
    if set(secrets) - allowed:
        reasons.append("UNRECOGNIZED_SECRET_ALIAS")
    for alias in allowed - {"MINERU_ENABLED"}:
        if (
            not isinstance(secrets.get(alias), str)
            or not secrets[alias]
            or "dummy" in secrets[alias].lower()
        ):
            reasons.append("MISSING_REAL_ALIAS_" + alias)
    if secrets.get("MINERU_ENABLED") != "true":
        reasons.append("MINERU_DISABLED")
    # 不创造counter依据。真实工厂仍会再次执行其正式守卫。
    if "profiles.json" in config_paths:
        profiles = load(config_paths["profiles.json"])
        for kind in ("embedding", "rerank"):
            candidates = [
                p
                for p in profiles
                if p["kind"] == kind and p["config"].get("adapter_kind") == "bailian"
            ]
            if not candidates or any(
                p["config"].get("counter_status") != "verified" for p in candidates
            ):
                reasons.append("INPUT_COUNTER_UNVERIFIED_" + kind)
    materials = plan.get("counter_evidence", [])
    if len(materials) < 3:
        reasons.append("THREE_CAPABILITY_COUNTER_EVIDENCE_REQUIRED")
    for material in materials:
        target = (base / material.get("file", "missing")).resolve()
        if (
            not target.is_relative_to(base)
            or not target.is_file()
            or digest(target.read_bytes()) != material.get("sha256")
        ):
            reasons.append("COUNTER_EVIDENCE_HASH_INVALID")
            continue
        evidence = load(target)
        if (
            evidence.get("status") != "verified"
            or evidence.get("capability") not in {"embedding", "rerank", "generation"}
            or not all(
                evidence.get(k)
                for k in ("model", "revision", "algorithm", "source", "date", "applicable_limits")
            )
            or not evidence.get("calibration_results")
            or not all(
                r.get("passed") is True and r.get("input_sha256")
                for r in evidence["calibration_results"]
            )
        ):
            reasons.append("COUNTER_EVIDENCE_INCOMPLETE")
    if {m.get("capability") for m in materials} != {"embedding", "rerank", "generation"}:
        reasons.append("COUNTER_CAPABILITIES_INCOMPLETE")
    if "models.json" in config_paths:
        models = load(config_paths["models.json"])
        if not any(
            p.get("provider_kind") == "openai_compatible" and p.get("tokenizer_kind") == "tiktoken"
            for p in models
        ):
            reasons.append("REAL_GENERATION_PROFILE_REQUIRED")
    budget = plan.get("budget", {})
    limits = {
        "cloud_jobs": 1,
        "document_chunks": 128,
        "queries": 2,
        "reranks": 2,
        "answers": 1,
        "max_output_tokens": 512,
        "timeout_seconds": 1200,
    }
    if plan_name == "Acceptance":
        limits.update(
            cloud_jobs=8,
            document_chunks=2048,
            queries=60,
            reranks=32,
            answers=3,
            timeout_seconds=3600,
        )
    if set(budget) != set(limits) or any(
        type(budget.get(k)) is not int or not 0 < budget[k] <= v for k, v in limits.items()
    ):
        reasons.append("LIVE_BUDGET_INVALID")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "plan_hash": digest(plan),
        "secrets": secrets,
        "config_paths": config_paths,
        "budget": budget,
        "approved_files": approved_files,
    }
