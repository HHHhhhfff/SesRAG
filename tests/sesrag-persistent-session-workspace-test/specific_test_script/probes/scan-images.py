"""QLT_006：只扫描本轮归档；只输出命中面和计数，绝不输出Secret值。"""

import json
import os
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit


def main():
    needles = [
        value.encode()
        for value in [
            os.environ["MODEL_API_KEY"],
            os.environ["PROVIDER_CONTROL_TOKEN"],
            unquote(urlsplit(os.environ["DATABASE_URL"]).password),
            os.environ["DATABASE_URL"],
        ]
    ]
    assert len(needles) == 4 and all(needles)
    archive = Path("/outputs/quality/secret-images.tar")
    matches = []
    members = 0

    def scan(stream, depth=0):
        nonlocal members
        with tarfile.open(fileobj=stream, mode="r|*") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                members += 1
                # 单层镜像可能数百MiB；流式匹配跨chunk秘密，嵌套层仅8MiB以内驻留内存。
                nested = depth < 2 and (
                    member.name.endswith(".tar") or member.name.startswith("blobs/")
                )
                with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as spool:
                    source = tar.extractfile(member)
                    carry = b""
                    hit = False
                    while block := source.read(64 * 1024):
                        data = carry + block
                        hit = hit or any(needle in data for needle in needles)
                        carry = data[-max(map(len, needles)) :]
                        if nested:
                            spool.write(block)
                    if hit:
                        matches.append(
                            {"depth": depth, "entry": member.name, "kind": "literal-secret"}
                        )
                    if nested:
                        spool.seek(0)
                        try:
                            scan(spool, depth + 1)
                        except tarfile.ReadError:
                            # 只有确实可解析的OCI JSON对象可免层解码；未知/损坏压缩层绝不算已扫描。
                            spool.seek(0)
                            value = spool.read(4 * 1024 * 1024 + 1)
                            if len(value) > 4 * 1024 * 1024:
                                raise RuntimeError("IMAGE_LAYER_UNDECODED") from None
                            try:
                                decoded = json.loads(value)
                            except (ValueError, UnicodeError):
                                raise RuntimeError("IMAGE_LAYER_UNDECODED") from None
                            if not isinstance(decoded, (dict, list)):
                                raise RuntimeError("IMAGE_LAYER_UNDECODED") from None

    with archive.open("rb") as stream:
        scan(stream)
    result = {
        "status": "passed" if not matches else "failed",
        "archive_bytes": archive.stat().st_size,
        "members_scanned": members,
        "secret_classes_checked": [
            "model_key",
            "control_token",
            "postgres_password",
            "database_url",
        ],
        "matches": matches,
    }
    Path("/outputs/quality/secret-image-scan.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    archive.unlink()
    print(json.dumps({"status": "passed", "scan_status": result["status"]}))


if __name__ == "__main__":
    main()
