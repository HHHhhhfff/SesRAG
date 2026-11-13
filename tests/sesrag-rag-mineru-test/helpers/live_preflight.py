"""真实计划的离线分能力门禁；不请求供应商，也不替代产品正式counter守卫。"""

import base64
import json
from pathlib import Path

from helpers.common import digest, load

CAPABILITIES = {"mineru", "embedding", "rerank", "generation"}
ALIASES = {
    "mineru": {
        "MINERU_ENABLED",
        "MINERU_API_KEY",
        "MINERU_STATE_ENCRYPTION_KEY",
        "MINERU_STORAGE_HOST_ALLOWLIST",
    },
    "embedding": {"RAG_EMBEDDING_API_KEY"},
    "rerank": {"RAG_RERANK_API_KEY"},
    "generation": {"MODEL_API_KEY"},
}
FORMATS = {".txt", ".md", ".doc", ".docx", ".pdf", ".xls", ".xlsx", ".ppt", ".pptx"}


def evaluate(path, plan_name, suite):
    base = (suite / "runtime-inputs").resolve()
    candidate = Path(path).resolve()
    if not candidate.is_relative_to(base) or candidate.suffix != ".json" or not candidate.is_file():
        raise ValueError("LIVE_PLAN_OUTSIDE_PRIVATE_INPUTS")
    plan = load(candidate)
    reasons, approved, paths = [], [], {}

    def private_file(relative):
        if not isinstance(relative, str):
            return None
        target = (base / relative).resolve()
        return target if target.is_relative_to(base) and target.is_file() else None

    if plan.get("schema_version") != 1 or plan.get("plan") != plan_name:
        reasons.append("LIVE_PLAN_IDENTITY")
    declared = plan.get("capabilities", sorted(CAPABILITIES))
    if (
        not isinstance(declared, list)
        or not declared
        or any(not isinstance(c, str) or c not in CAPABILITIES for c in declared)
        or len(declared) != len(set(declared))
    ):
        reasons.append("LIVE_CAPABILITIES_INVALID")
        capabilities = set()
    else:
        capabilities = set(declared)
    full = capabilities == CAPABILITIES
    if plan_name == "Acceptance" and not full:
        reasons.append("ACCEPTANCE_REQUIRES_ALL_CAPABILITIES")
    if plan.get("authorized") is not True or (
        "mineru" in capabilities and plan.get("consent_version") != "mineru-office-outbound-v1"
    ):
        reasons.append("OUTBOUND_AUTHORIZATION_REQUIRED")
    for row in plan.get("files", []):
        target = private_file(row.get("file"))
        if target is None or digest(target.read_bytes()) != row.get("sha256"):
            reasons.append("LIVE_FILE_HASH_INVALID")
            continue
        if "local-only" in target.parts:
            reasons.append("UNSAFE_LIVE_FIXTURE")
        if not 0 < target.stat().st_size <= 10 * 1024**2 or target.suffix.lower() not in FORMATS:
            reasons.append("LIVE_FILE_FORMAT_OR_SIZE_INVALID")
        approved.append({"source": target, "sha256": row["sha256"], "filename": target.name})
    if capabilities & {"mineru", "embedding"} and not approved:
        reasons.append("LIVE_FILES_REQUIRED")
    required_configs = {"profiles.json"} if capabilities - {"generation"} else set()
    if "generation" in capabilities:
        required_configs.add("models.json")
    configs, config_hashes = {}, {}
    for name in sorted(required_configs):
        target = private_file(plan.get("config_files", {}).get(name))
        if target is None:
            reasons.append("REAL_CONFIG_MISSING_" + name)
        else:
            # 校验和冻结必须消费同一份有界字节，避免校验A却冻结后来替换的B。
            with target.open("rb") as source:
                raw = source.read(4 * 1024**2 + 1)
            if len(raw) > 4 * 1024**2:
                raise ValueError("JSON_INPUT_LIMIT")
            paths[name], configs[name] = target, json.loads(raw.decode("utf-8-sig"))
            config_hashes[name] = digest(raw)
    private = private_file(plan.get("secret_file"))
    supplied = load(private) if private else {}
    allowed = set().union(*ALIASES.values())
    if set(supplied) - allowed:
        reasons.append("UNRECOGNIZED_SECRET_ALIAS")
    selected_aliases = set().union(*(ALIASES[c] for c in capabilities))
    secrets = {k: v for k, v in supplied.items() if k in selected_aliases}
    for alias in sorted(selected_aliases - {"MINERU_ENABLED"}):
        value = secrets.get(alias)
        if not isinstance(value, str) or not value.strip() or "dummy" in value.lower():
            reasons.append("MISSING_REAL_ALIAS_" + alias)
    if "mineru" in capabilities:
        if secrets.get("MINERU_ENABLED") != "true":
            reasons.append("MINERU_DISABLED")
        try:
            if (
                len(base64.b64decode(secrets.get("MINERU_STATE_ENCRYPTION_KEY", ""), validate=True))
                != 32
            ):
                raise ValueError
        except (ValueError, TypeError):
            reasons.append("MINERU_STATE_KEY_INVALID")
    # 每种能力单独选择真实Profile；未选能力的模板不会解除其unverified状态。
    models = {}
    for kind in sorted(capabilities & {"embedding", "rerank"}):
        rows = [
            p
            for p in configs.get("profiles.json", [])
            if p.get("kind") == kind and p.get("config", {}).get("adapter_kind") == "bailian"
        ]
        if not rows or any(p["config"].get("counter_status") != "verified" for p in rows):
            reasons.append("INPUT_COUNTER_UNVERIFIED_" + kind)
        models[kind] = {
            (
                p["config"].get("space", {}).get("model")
                if kind == "embedding"
                else p["config"].get("model", "qwen3.7-text-rerank")
            )
            for p in rows
        }
    if "mineru" in capabilities and not any(
        p.get("kind") == "parser" and p.get("config", {}).get("parser_kind") == "mineru"
        for p in configs.get("profiles.json", [])
    ):
        reasons.append("REAL_MINERU_PROFILE_REQUIRED")
    if "generation" in capabilities:
        rows = [
            p
            for p in configs.get("models.json", [])
            if p.get("provider_kind") == "openai_compatible"
            and p.get("tokenizer_kind") == "tiktoken"
            and p.get("status") == "enabled"
        ]
        if not rows:
            reasons.append("REAL_GENERATION_PROFILE_REQUIRED")
        models["generation"] = {p.get("model_name") for p in rows}
    counter_kinds = capabilities - {"mineru"}
    seen = set()
    for row in plan.get("counter_evidence", []):
        kind = row.get("capability")
        if kind not in counter_kinds:
            continue
        target = private_file(row.get("file"))
        if target is None or digest(target.read_bytes()) != row.get("sha256"):
            reasons.append("COUNTER_EVIDENCE_HASH_INVALID")
            continue
        evidence = load(target)
        if kind in seen:
            reasons.append("COUNTER_EVIDENCE_DUPLICATE_" + kind)
        seen.add(kind)
        if (
            evidence.get("status") != "verified"
            or evidence.get("capability") != kind
            or not all(
                evidence.get(k)
                for k in ("model", "revision", "algorithm", "source", "date", "applicable_limits")
            )
            or not evidence.get("calibration_results")
            or not all(
                r.get("passed") is True and len(r.get("input_sha256", "")) == 64
                for r in evidence["calibration_results"]
            )
        ):
            reasons.append("COUNTER_EVIDENCE_INCOMPLETE_" + kind)
        if evidence.get("model") not in models.get(kind, set()):
            reasons.append("COUNTER_EVIDENCE_MODEL_MISMATCH_" + kind)
    reasons.extend("COUNTER_EVIDENCE_MISSING_" + kind for kind in sorted(counter_kinds - seen))
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
    budget = plan.get("budget", {})
    output_limit = budget.get("max_output_tokens", 0)
    output_limit = output_limit if type(output_limit) is int else 0
    if "generation" in capabilities and any(
        type(row.get("max_output_tokens")) is not int or row["max_output_tokens"] > output_limit
        for row in configs.get("models.json", [])
        if row.get("provider_kind") == "openai_compatible" and row.get("status") == "enabled"
    ):
        reasons.append("GENERATION_OUTPUT_BUDGET_EXCEEDED")
    if (
        set(budget) != set(limits)
        or any(type(budget.get(k)) is not int or not 0 <= budget[k] <= v for k, v in limits.items())
        or budget.get("timeout_seconds", 0) <= 0
    ):
        reasons.append("LIVE_BUDGET_INVALID")
    operation_capability = {
        "cloud_jobs": "mineru",
        "document_chunks": "embedding",
        "queries": "embedding",
        "reranks": "rerank",
        "answers": "generation",
        "max_output_tokens": "generation",
    }
    effective_budget = dict(budget)
    for operation, capability in operation_capability.items():
        if capability not in capabilities:
            effective_budget[operation] = 0
        elif budget.get(operation, 0) <= 0:
            reasons.append("LIVE_BUDGET_REQUIRED_" + operation)
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "plan_hash": digest(plan),
        "capabilities": sorted(capabilities),
        "full_business_scope": full,
        "secrets": secrets,
        "config_paths": paths,
        "config_hashes": config_hashes,
        "budget": effective_budget,
        "approved_files": approved,
    }
