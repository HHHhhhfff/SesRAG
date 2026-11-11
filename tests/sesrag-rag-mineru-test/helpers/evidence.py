"""脱敏、有界证据与可复核索引；不归档完整环境或Prompt。"""

import re
from pathlib import Path

from helpers.common import digest, write


def redact(text, secrets=()):
    for value in sorted(set(secrets), key=len, reverse=True):
        if value:
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"(?i)Bearer\s+[^\s\"',]+", "Bearer [REDACTED]", text)
    text = re.sub(r"postgresql[^\s\"']+", "[PRIVATE_DSN]", text)
    text = re.sub(r"https?://[^\s\"<>]+\?[^\s\"<>]+", "[CAPABILITY_URL]", text)
    text = re.sub(r"[A-Za-z]:[\\/][^\s\"']+", "[HOST_PATH]", text)
    return text


def save_log(path, raw, secrets=(), limit=5 * 1024**2):
    data = redact(raw, secrets).encode("utf-8")
    if len(data) > limit:
        raise ValueError("EVIDENCE_TRUNCATED")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def scan(root, secrets=()):
    findings = []
    total = 0
    for path in Path(root).rglob("*"):
        if not path.is_file():
            continue
        total += path.stat().st_size
        if path.stat().st_size > 20 * 1024**2 or total > 200 * 1024**2:
            raise ValueError("EVIDENCE_STORAGE_LIMIT")
        raw = path.read_bytes()
        if any(s and s.encode() in raw for s in secrets):
            findings.append(path.name)
        text = raw.decode("utf-8", errors="replace")
        if re.search(r"https?://\S+(?:X-Amz-Signature|Signature|access_token)=", text, re.I):
            findings.append(path.name)
    if findings:
        raise ValueError("EVIDENCE_SECRET_LEAK: " + ",".join(set(findings)))


def index(root):
    root = Path(root)
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "evidence-index.json":
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path.read_bytes()),
                }
            )
    write(root / "evidence-index.json", {"schema_version": 1, "files": files})
