"""显式真实探针：只上传固定公开/合成样本，检查点恢复同batch，不自动启用Profile。"""

import argparse
import asyncio
import hashlib
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from backend.application.errors import ApplicationError
from backend.config import Settings
from backend.domain.rag import OFFICE_FORMATS
from backend.domain.rag_profiles import EmbeddingConfig, ParserConfig, RerankConfig
from backend.infrastructure.providers.bailian_embedding import BailianEmbedding
from backend.infrastructure.providers.bailian_rerank import BailianRerank
from backend.infrastructure.rag.artifact_store import ArtifactStore
from backend.infrastructure.rag.isolated_processing import isolated
from backend.infrastructure.rag.mineru_client import MinerUClient

MODEL_ORIGIN = "https://dashscope.aliyuncs.com"


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


async def probe_models(origin=MODEL_ORIGIN):
    embedding = EmbeddingConfig(
        adapter_kind="bailian",
        base_url=origin + "/compatible-mode/v1",
        config_ref="env:RAG_EMBEDDING_API_KEY",
        space={
            "provider": "bailian",
            "model": "qwen3.7-text-embedding",
            "revision": "explicit_probe_20261030",
            "dimension": 1024,
            "normalization": "l2_float32_v1",
        },
    )
    rerank = RerankConfig(
        adapter_kind="bailian",
        endpoint=origin + "/api/v1/services/rerank/text-rerank/text-rerank",
        config_ref="env:RAG_RERANK_API_KEY",
    )
    texts = (
        "SesRAG stores facts in PostgreSQL and vectors in pgvector.",
        "The moon orbits the Earth.",
    )
    result = {}
    for kind in ("embedding", "rerank"):
        try:
            secret = os.getenv(
                "RAG_EMBEDDING_API_KEY" if kind == "embedding" else "RAG_RERANK_API_KEY"
            )
            if not secret:
                raise ApplicationError("MODEL_CREDENTIAL_UNAVAILABLE", "探针缺凭据", 409)
            if kind == "embedding":
                adapter = BailianEmbedding(embedding, secret)
                vectors = await adapter.embed(texts)
                query = await adapter.embed(("Which database does SesRAG use?",), purpose="query")
                result[kind] = {
                    "state": "protocol_passed",
                    "documents": len(vectors),
                    "query_vectors": len(query),
                    "dimension": len(vectors[0]),
                    "counter_status": "unverified",
                }
            else:
                ranking = await BailianRerank(rerank, secret).rank(
                    "Which database does SesRAG use?", texts
                )
                result[kind] = {
                    "state": "protocol_passed",
                    "ranking": [index for index, _ in ranking],
                    "counter_status": "unverified",
                }
        except ApplicationError as exc:
            result[kind] = {"state": "limited", "error_code": exc.code}
    return result


async def probe_office(settings, fixture_root, output, state_root, *, resume_known_batches=False):
    manifest = json.loads((fixture_root / "manifest.json").read_text(encoding="utf-8"))
    checkpoint = state_root / "checkpoint.json"
    report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"office": {}}
    states = json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else {}
    store = ArtifactStore(state_root, settings.mineru_state_encryption_key)
    config = ParserConfig(
        parser_kind="mineru",
        formats=tuple(sorted(OFFICE_FORMATS)),
        output_protocol="mineru_cloud_v4_office_text_v1",
    )
    for entry in manifest["files"]:
        source = (fixture_root / entry["file"]).resolve()
        if source.parent != fixture_root.resolve() or source.suffix not in OFFICE_FORMATS:
            continue
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("探针样本hash不符，不外发")
        state = states.get(source.name)
        if (
            resume_known_batches
            and state
            and state["phase"] == "failed"
            and report.get("office", {}).get(source.name, {}).get("error_code")
            == "OUTBOUND_TARGET_UNSAFE"
            and store.path(state["job_id"] + ".bin").exists()
        ):
            # 仅P0探针：人工/操作者核实域后读取同一batch，不更改产品的失败Job，不重新提交原件。
            report.setdefault("probe_history", []).append(
                {
                    "file": source.name,
                    "error_code": "OUTBOUND_TARGET_UNSAFE",
                    "action": "explicit_same_batch_read_after_host_review",
                }
            )
            state["phase"] = "uploaded"
        if state and state["phase"] in {"completed", "failed", "unknown"}:
            continue
        gateway = MinerUClient(settings)
        try:
            await isolated("validate", raw, source.suffix, filename=source.name)
            if state and state["phase"] == "submitting":
                raise ApplicationError("MINERU_SUBMISSION_UNKNOWN", "未确认的提交不重发", 409)
            if state is None:
                state = {"phase": "submitting", "job_id": str(uuid4()), "started": time.time()}
                states[source.name] = state
                write_report(checkpoint, states)
                handle = await gateway.submit(
                    {
                        "filename": source.name,
                        "parse_job_id": state["job_id"],
                        "config": config.model_dump(),
                    }
                )
                store.save_state(state["job_id"] + ".bin", handle)
                state["phase"] = "allocated"
                write_report(checkpoint, states)
            handle = store.load_state(state["job_id"] + ".bin")
            deadline = state["started"] + 300
            for count in range(60):
                if time.time() >= deadline:
                    raise ApplicationError("MINERU_ATTEMPT_TIMEOUT", "探针超时", 422)
                observed = await gateway.poll(handle)
                if observed["state"] == "waiting-file":
                    await gateway.upload(raw, handle)
                    state["phase"] = "uploaded"
                    write_report(checkpoint, states)
                elif observed["state"] == "done":
                    handle["download_url"] = observed["download_url"]
                    result = await gateway.download(handle)
                    artifact = await isolated("package", result, source.suffix, timeout=60)
                    store.write(
                        "normalized-" + state["job_id"] + ".bin",
                        json.dumps(asdict(artifact), ensure_ascii=False).encode(),
                    )
                    report["office"][source.name] = {
                        "state": "parsed",
                        "format": source.suffix,
                        "source_sha256": entry["sha256"],
                        "text_sha256": hashlib.sha256(artifact.text.encode()).hexdigest(),
                        "characters": len(artifact.text),
                        "blocks": len(artifact.blocks),
                        "verified_source_positions": sum(
                            p.get("quality") == "verified"
                            for b in artifact.blocks
                            for p in b.locations
                        ),
                        "normalization_protocol": artifact.protocol,
                        "polls": count + 1,
                    }
                    state["phase"] = "completed"
                    break
                elif observed["state"] == "failed":
                    raise ApplicationError("MINERU_PARSE_FAILED", "远端明确失败", 422)
                await asyncio.sleep(5)
            else:
                raise ApplicationError("MINERU_ATTEMPT_TIMEOUT", "探针轮询超限", 422)
        except ApplicationError as exc:
            if state:
                state["phase"] = "unknown" if exc.code == "MINERU_SUBMISSION_UNKNOWN" else "failed"
            report["office"][source.name] = {
                "state": "limited",
                "format": source.suffix,
                "error_code": exc.code,
            }
        write_report(checkpoint, states)
        write_report(output, report)
    return report


async def read_known_results(settings, state_root, output):
    """P0独立只读补证：读取已有batch的done产物，不复活产品Job、不重提源文件。"""
    store = ArtifactStore(state_root, settings.mineru_state_encryption_key)
    states = json.loads((state_root / "checkpoint.json").read_text(encoding="utf-8"))
    report = {"mode": "read_existing_remote_results_after_host_review", "office": {}}
    for name, state in states.items():
        try:
            gateway = MinerUClient(settings)
            handle = store.load_state(state["job_id"] + ".bin")
            observed = await gateway.poll(handle)
            if observed["state"] != "done":
                raise ApplicationError("MINERU_RESULT_UNAVAILABLE", "原批次未完成或结果已过期", 422)
            handle["download_url"] = observed["download_url"]
            raw = await gateway.download(handle)
            artifact = await isolated("package", raw, Path(name).suffix, timeout=60)
            store.write(
                "normalized-" + state["job_id"] + ".bin",
                json.dumps(asdict(artifact), ensure_ascii=False).encode(),
            )
            report["office"][name] = {
                "state": "parsed",
                "format": Path(name).suffix,
                "characters": len(artifact.text),
                "blocks": len(artifact.blocks),
                "text_sha256": hashlib.sha256(artifact.text.encode()).hexdigest(),
                "verified_source_positions": sum(
                    p.get("quality") == "verified" for b in artifact.blocks for p in b.locations
                ),
                "protocol": artifact.protocol,
            }
        except ApplicationError as exc:
            report["office"][name] = {"state": "limited", "error_code": exc.code}
        write_report(output, report)
    return report


async def main(args):
    if not args.allow_synthetic_outbound:
        raise SystemExit("真实探针需显式 --allow-synthetic-outbound，仅限固定公开/合成样本")
    output = Path(args.output).resolve()
    if args.mode == "models":
        result = {"models": await probe_models(args.model_origin)}
    elif args.mode == "office":
        result = await probe_office(
            Settings(),
            Path("tests/fixtures/rag-v3").resolve(),
            output,
            output.parent / "private",
            resume_known_batches=args.resume_known_batches,
        )
    else:
        result = await read_known_results(Settings(), output.parent / "private", output)
    write_report(output, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("models", "office", "office-results"), required=True)
    parser.add_argument("--allow-synthetic-outbound", action="store_true")
    parser.add_argument("--model-origin", default=MODEL_ORIGIN)
    parser.add_argument("--resume-known-batches", action="store_true")
    parser.add_argument("--output", default="data/rag-implementation/real-provider-report.json")
    asyncio.run(main(parser.parse_args()))
