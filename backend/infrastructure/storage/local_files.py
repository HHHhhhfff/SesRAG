import hashlib
from pathlib import Path


class LocalFileStorage:
    """将上传文件保存到 API 与 Worker 共享的目录，不暴露宿主绝对路径。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, document_id: str, extension: str, content: bytes) -> tuple[str, str]:
        content_hash = hashlib.sha256(content).hexdigest()
        storage_key = f"documents/{document_id}/source{extension}"
        target = self.root / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        return storage_key, content_hash

    def read(self, storage_key: str) -> bytes:
        target = (self.root / storage_key).resolve()
        if self.root.resolve() not in target.parents:
            raise ValueError("storage key escapes upload root")
        return target.read_bytes()
