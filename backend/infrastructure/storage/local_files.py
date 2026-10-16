import hashlib
from contextlib import suppress
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
        try:
            temporary.write_bytes(content)
            temporary.replace(target)
        except OSError:
            # 只清理由本次 UUID 保存拥有的文件，不递归删除共享目录。
            for owned in (temporary, target):
                with suppress(OSError):
                    owned.unlink(missing_ok=True)
            with suppress(OSError):
                target.parent.rmdir()
            raise
        return storage_key, content_hash

    def read(self, storage_key: str) -> bytes:
        return self.resolve(storage_key).read_bytes()

    def resolve(self, storage_key: str) -> Path:
        target = (self.root / storage_key).resolve()
        if self.root.resolve() not in target.parents:
            raise ValueError("storage key escapes upload root")
        return target

    def remove(self, storage_key: str) -> None:
        target = self.resolve(storage_key)
        target.unlink(missing_ok=True)
        with suppress(OSError):
            target.parent.rmdir()
