"""私有状态文件原子替换；能力URL只以AES-GCM密文保存。"""

import base64
import json
import os
import re
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.application.errors import PermanentTaskError


class ArtifactStore:
    def __init__(self, root, encryption_key=None):
        self.root = Path(root).resolve()
        self.encryption_key = encryption_key

    def path(self, key):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,120}\.bin", key):
            raise PermanentTaskError("ARTIFACT_PATH_INVALID", "产物身份无效")
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise PermanentTaskError("ARTIFACT_PATH_INVALID", "产物超出私有范围")
        return target

    def write(self, key, content):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        try:
            with temporary.open("wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise PermanentTaskError("RAG_STORAGE_EXHAUSTED", "私有产物写入失败") from None
        return key

    def read(self, key, *, limit=100 * 1024**2):
        path = self.path(key)
        try:
            if path.stat().st_size > limit:
                raise PermanentTaskError("ARTIFACT_LIMIT", "私有产物超过上限")
            return path.read_bytes()
        except OSError:
            raise PermanentTaskError("ARTIFACT_UNAVAILABLE", "私有产物不可用") from None

    def cipher(self):
        try:
            key = base64.b64decode(self.encryption_key or "", validate=True)
            if len(key) != 32:
                raise ValueError()
            return AESGCM(key)
        except ValueError:
            raise PermanentTaskError("MINERU_PROFILE_UNAVAILABLE", "私有状态加密配置无效") from None

    def save_state(self, key, value):
        nonce = os.urandom(12)
        raw = json.dumps(value, ensure_ascii=False).encode()
        if len(raw) > 1024**2:
            raise PermanentTaskError("ARTIFACT_LIMIT", "私有状态过大")
        return self.write(key, nonce + self.cipher().encrypt(nonce, raw, key.encode()))

    def load_state(self, key):
        raw = self.read(key, limit=2 * 1024**2)
        try:
            return json.loads(self.cipher().decrypt(raw[:12], raw[12:], key.encode()))
        except Exception:
            raise PermanentTaskError("MINERU_STATE_UNAVAILABLE", "私有状态无法恢复") from None
