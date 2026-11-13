"""只复制hash核实的PRD-003输入，并生成有界、不可执行的local边界数据。"""

import io
import json
import shutil
import zipfile
from pathlib import Path


def materialize(root, destination):
    import hashlib

    root, destination = Path(root), Path(destination)
    source = root / "tests/fixtures/rag-v3"
    manifest_raw = (source / "manifest.json").read_bytes()
    selection = json.loads(
        (root / "tests/sesrag-rag-mineru-test/fixtures/manifest.json").read_text(encoding="utf-8")
    )
    if hashlib.sha256(manifest_raw).hexdigest() != selection["source_manifest_sha256"]:
        raise ValueError("FIXTURE_MANIFEST_CHANGED")
    declared = json.loads(manifest_raw)
    destination.mkdir(parents=True, exist_ok=True)
    results = []
    for row in declared["files"]:
        path = (source / row["file"]).resolve()
        if path.parent != source.resolve() or not path.is_file():
            raise ValueError("FIXTURE_PATH_INVALID")
        raw = path.read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("FIXTURE_HASH_CHANGED")
        shutil.copyfile(path, destination / row["file"])
        results.append(row)
    for name in ("NOTICE.md", "NOTICE", "LICENSE", "LICENSE-APACHE-2.0.txt", "README.md"):
        if (source / name).is_file():
            shutil.copyfile(source / name, destination / name)
    boundary = destination / "local-only"
    boundary.mkdir(exist_ok=True)
    values = {
        "empty.txt": b"",
        "invalid-encoding.txt": b"\xff\xfe\x00",
        "unicode.txt": ("合成边界 Unicode 🙂\n" * 800).encode(),
        "cross-chunk.txt": (
            "Synthetic fact: code ALPHA appears first.\n" * 25 + "The answer is 37.\n"
        ).encode(),
        "untrusted.md": b"<script>do_not_execute()</script>\n![remote](https://invalid.example/a.png)",
    }
    for delta in (-1, 0, 1):
        values[f"size-{delta + 1}.txt"] = b"A" * (10 * 1024**2 + delta)
    for name, member in (("escape.zip", "../escape.txt"), ("nested.zip", "other.zip")):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(member, b"synthetic non executable content")
            archive.writestr("full.md", b"# Safe synthetic fixture\nNo real data.")
        values[name] = stream.getvalue()
    duplicate = io.BytesIO()
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("full.md", b"first")
        archive.writestr("FULL.md", b"conflicting normalized name")
    values["duplicate.zip"] = duplicate.getvalue()
    for name, raw in values.items():
        (boundary / name).write_bytes(raw)
    result = {
        "source_files": results,
        "local_only": [
            {
                "file": f"local-only/{name}",
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for name, raw in values.items()
        ],
        "paid_upload_allowed": False,
    }
    (destination / "materialized.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
