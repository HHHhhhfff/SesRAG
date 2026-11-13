"""构建/冻结可恢复镜像内容；第二轮不依赖已删除的唯一image ID。"""

import json
import shutil

from helpers.common import SUITE, command, load, write
from helpers.evidence import save_log


def save_ledger(path, ledger):
    write(path, ledger)


def images(ledger, ledger_path, fingerprints, frozen=None):
    tags = {
        kind: f"sesrag-rag-test:{ledger['run_id']}-{kind}" for kind in ("app", "frontend", "tools")
    }
    ledger["images"] = [{"tag": tag, "id": None} for tag in tags.values()]
    save_ledger(ledger_path, ledger)  # 构建/加载之前先写镜像意图。
    report_dir = ledger_path.parent
    if frozen:
        cache = (SUITE / ".cache/frozen-builds" / frozen).resolve()
        if cache.parent != (SUITE / ".cache/frozen-builds").resolve():
            raise ValueError("FROZEN_BUILD_PATH_INVALID")
        saved = load(cache / "build.json")
        if saved["build_source"] != fingerprints["build_source"]:
            raise ValueError("FROZEN_SOURCE_MISMATCH")
        for kind, tag in tags.items():
            row = saved["images"][kind]
            archive = (cache / row["archive"]).resolve()
            if archive.parent != cache:
                raise ValueError("FROZEN_ARCHIVE_PATH_INVALID")
            import hashlib

            with archive.open("rb") as source:
                valid_hash = hashlib.file_digest(source, "sha256").hexdigest()
            if valid_hash != row["sha256"]:
                raise ValueError("FROZEN_ARCHIVE_HASH_INVALID")
            target_row = next(r for r in ledger["images"] if r["tag"] == tag)
            target_row["id"] = row["id"]
            old_code, old_raw = command(["docker", "image", "inspect", row["tag"]], check=False)
            existed = old_code == 0
            if existed and json.loads(old_raw)[0]["Id"] != row["id"]:
                raise ValueError("FROZEN_ORIGINAL_TAG_CONFLICT")
            if not existed:
                # load会恢复归档原tag；意图先落盘，加载/改tag中途强停仍可精确回收。
                ledger.setdefault("temporary_import_tags", []).append(
                    {"tag": row["tag"], "id": row["id"], "absent_before_load": True}
                )
            save_ledger(ledger_path, ledger)
            command(["docker", "image", "load", "-i", archive], timeout=300)
            command(["docker", "image", "tag", row["id"], tag])
            # 归档里的原tag仅在本次load新增时移除；不能删别人的既有引用。
            if row["tag"] != tag and not existed:
                command(["docker", "image", "rm", row["tag"]])
    else:
        for kind in tags:
            print(f"[{ledger['run_id']}] 构建 {kind} 镜像（首次准备可能较久）", flush=True)
            dockerfile = {
                "app": "docker/api/Dockerfile",
                "frontend": "docker/frontend/Dockerfile",
                "tools": "tests/sesrag-rag-mineru-test/compose/Dockerfile.tools",
            }[kind]
            args = ["docker", "build", "--progress", "plain", "-t", tags[kind], "-f", dockerfile]
            for key, value in {
                "sesrag.test.suite": "rag-mineru-003",
                "sesrag.test.run": ledger["run_id"],
                "sesrag.test.owner": ledger["owner"],
            }.items():
                args.extend(["--label", f"{key}={value}"])
            if kind == "tools":
                args.extend(["--build-arg", f"APP_IMAGE={tags['app']}"])
            # 首次Chromium及系统库下载可能较慢；保持一小时硬截止，缓存复跑无需重下。
            code, raw = command([*args, "."], timeout=3600, check=False)
            save_log(report_dir / f"build-{kind}.log", raw)
            if code:
                raise ValueError(f"BUILD_FAILED_{kind}")
    for row in ledger["images"]:
        info = json.loads(command(["docker", "image", "inspect", row["tag"]])[1])[0]
        row["id"] = info["Id"]
        row["size_bytes"] = info["Size"]
    save_ledger(ledger_path, ledger)
    return tags


def freeze(ledger, fingerprints, tags):
    identity = fingerprints["build_source"][:24]
    directory = SUITE / ".cache/frozen-builds" / identity
    if (directory / "build.json").exists():
        return identity
    cache = SUITE / ".cache/frozen-builds"
    used = sum(p.stat().st_size for p in cache.rglob("*") if p.is_file()) if cache.exists() else 0
    size = sum(row.get("size_bytes", 0) for row in ledger["images"])
    if used + size > 10 * 1024**3 or shutil.disk_usage(SUITE).free < size + 2 * 1024**3:
        raise ValueError("FROZEN_CACHE_BUDGET_EXCEEDED")
    directory.mkdir(parents=True, exist_ok=False)
    data = {"build_source": fingerprints["build_source"], "images": {}}
    for kind, tag in tags.items():
        row = next(r for r in ledger["images"] if r["tag"] == tag)
        archive = directory / f"{kind}.tar"
        command(["docker", "image", "save", "-o", archive, tag], timeout=300)
        # 流式核对归档，避免把镜像内容整体读入内存或报告。
        import hashlib

        with archive.open("rb") as source:
            sha = hashlib.file_digest(source, "sha256").hexdigest()
        data["images"][kind] = {"id": row["id"], "tag": tag, "archive": archive.name, "sha256": sha}
    write(directory / "build.json", data)
    return identity
