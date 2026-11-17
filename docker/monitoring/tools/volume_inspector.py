"""受控卷检查和归档工具；无Docker socket，不读取任何应用卷。"""

import argparse
import json
import shutil
import tarfile
from pathlib import Path, PurePosixPath


def safe(members):
    total = 0
    for m in members:
        name = m.name.replace("\\", "/")
        if (
            PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or ":" in name
            or not (m.isfile() or m.isdir())
        ):
            raise ValueError("unsafe_archive")
        total += m.size
        if total > 12 * 1024**3:
            raise ValueError("archive_budget")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["stats", "backup", "restore", "files"])
    p.add_argument("--name")
    a = p.parse_args()
    if a.action == "files":
        print(
            json.dumps(
                [
                    p.relative_to("/source").as_posix()
                    for p in Path("/source").rglob("*")
                    if p.is_file()
                ]
            )
        )
        return
    if a.action == "stats":
        budgets = {
            "grafana_data": 0.5,
            "prometheus_data": 3,
            "loki_data": 3,
            "tempo_data": 3,
            "alloy_data": 0.5,
        }
        result = []
        for v in Path("/volumes").iterdir():
            size = sum(f.stat().st_size for f in v.rglob("*") if f.is_file() and not f.is_symlink())
            ratio = size / (budgets[v.name] * 1024**3)
            result.append(
                {
                    "volume": v.name,
                    "logical_bytes": size,
                    "budget_gib": budgets[v.name],
                    "budget_ratio": ratio,
                    "budget_state": "warning"
                    if ratio >= 0.85
                    else "hint"
                    if ratio >= 0.7
                    else "normal",
                    "filesystem_free_bytes": shutil.disk_usage(v).free,
                }
            )
        print(json.dumps(result))
        return
    if a.name not in {"grafana_data", "prometheus_data", "loki_data", "tempo_data", "alloy_data"}:
        raise ValueError("unknown_volume")
    archive = Path("/backup") / (a.name + ".tar.gz")
    if a.action == "backup":
        with tarfile.open(archive, "w:gz", dereference=False) as t:
            t.add("/source", arcname=".", recursive=False)
            for f in sorted(Path("/source").rglob("*")):
                if f.is_symlink():
                    raise ValueError("source_link")
                t.add(f, arcname=f.relative_to("/source").as_posix(), recursive=False)
    else:
        target = Path("/target")
        if any(target.iterdir()):
            raise ValueError("target_not_empty")
        with tarfile.open(archive) as t:
            safe(t.getmembers())
            t.extractall(target)
    print(json.dumps({"action": a.action, "volume": a.name, "status": "passed"}))


if __name__ == "__main__":
    main()
