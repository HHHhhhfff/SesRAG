"""主进程硬停后的账本恢复：锁未释放的活动运行不会被清理。"""

import json
import os
import re
import shutil
import subprocess


def lock_file(path):
    stream = path.open("a+b")
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            stream.close()
            raise
    else:
        import fcntl

        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return stream


def recover_stale(suite):
    root = (suite / "runtime").resolve()
    if not root.exists():
        return
    for ledger in root.glob("*/ledger.json"):
        directory = ledger.parent.resolve()
        if directory.parent != root:
            continue
        try:
            lease = lock_file(directory / "run.lock")
        except OSError:
            continue
        try:
            data = json.loads(ledger.read_text())
            project = data.get("project", "")
            if data.get("suite") != "observability-004" or not re.fullmatch(
                r"obs004-[a-z0-9_-]{1,60}", project
            ):
                continue
            # 只使用固定Compose和该账本的env；project归属必须与目录名一致。
            if project != "obs004-" + directory.name.lower():
                continue
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "--project-name",
                    project,
                    "--env-file",
                    str(directory / "test.env"),
                    "-f",
                    str(suite / "compose/compose.yaml"),
                    "down",
                    "--volumes",
                    "--remove-orphans",
                ],
                capture_output=True,
                timeout=90,
            )
            if result.returncode:
                raise RuntimeError("遗留测试资源回收失败")
        finally:
            lease.close()
        # 解析失败不会到达此处；目录已核验为本套件runtime直接子目录。
        shutil.rmtree(directory)
        print("[Recovery] 已回收中断运行 " + directory.name, flush=True)
