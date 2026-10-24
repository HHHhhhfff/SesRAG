"""Mock 与显式 tiktoken 计数器实现。"""

import base64
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import tiktoken

# 与Docker构建预热资产配对；扩展encoding时须同时明确资产hash并预备缓存。
ENCODING_ASSETS = {
    "cl100k_base": (
        "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken",
        "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7",
    )
}


@lru_cache(maxsize=8)
def _load_cached_encoding(encoding_name: str, cache_dir: str):
    asset = ENCODING_ASSETS.get(encoding_name)
    if asset is None or not cache_dir:
        raise ValueError("不支持的encoding或离线缓存不可用")
    url, expected_hash = asset
    filename = hashlib.sha1(url.encode()).hexdigest()
    try:
        with (Path(cache_dir) / filename).open("rb") as source:
            data = source.read(4 * 1024 * 1024 + 1)
    except OSError:
        raise ValueError("离线encoding缓存缺失或不可读") from None
    if len(data) > 4 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError("离线encoding缓存损坏")
    # 只有确认构建/安装阶段提供的完整资产存在后才进入SDK，避免普通cache miss隐式联网。
    return tiktoken.get_encoding(encoding_name)


def load_encoding_offline(encoding_name: str):
    cache_dir = os.environ.get(
        "TIKTOKEN_CACHE_DIR",
        os.environ.get("DATA_GYM_CACHE_DIR", str(Path(tempfile.gettempdir()) / "data-gym-cache")),
    )
    return _load_cached_encoding(encoding_name, cache_dir)


@dataclass(frozen=True, slots=True)
class CounterMessage:
    role: str
    content: str


class MockTokenCounter:
    """以稳定的词法边界计数，供离线 Profile 和边界测试使用。"""

    def __init__(self, version: str = "mock-tokenizer@1") -> None:
        self.version = version

    def count_text(self, text: str) -> int:
        return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))

    def count_messages(self, messages) -> int:
        return sum(self.count_text(item.content) + 4 for item in messages) + 2


class TikTokenCounter:
    """只接受显式 encoding，未知名称由 tiktoken 拒绝。"""

    def __init__(
        self,
        encoding_name: str,
        *,
        message_overhead_tokens: int,
        request_overhead_tokens: int,
        calibration_version: str,
        profile_tokenizer_version: str,
    ) -> None:
        if (
            not encoding_name
            or type(message_overhead_tokens) is not int
            or message_overhead_tokens < 0
            or type(request_overhead_tokens) is not int
            or request_overhead_tokens < 0
            or not isinstance(calibration_version, str)
            or not calibration_version.strip()
            or not isinstance(profile_tokenizer_version, str)
            or not profile_tokenizer_version.strip()
        ):
            raise ValueError("tokenizer 配置无效")
        self.encoding_name = encoding_name
        self.message_overhead_tokens = message_overhead_tokens
        self.request_overhead_tokens = request_overhead_tokens
        self._encoding = load_encoding_offline(encoding_name)
        identity_config = json.dumps(
            {
                "kind": "tiktoken",
                "package_version": tiktoken.__version__,
                "encoding_name": encoding_name,
                "message_overhead_tokens": message_overhead_tokens,
                "request_overhead_tokens": request_overhead_tokens,
                "calibration_version": calibration_version,
                "profile_tokenizer_version": profile_tokenizer_version,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        # 192 位摘要编码后为 32 字符；加版本前缀仍适配持久化的 40 字符上限。
        digest = hashlib.sha256(identity_config.encode("utf-8")).digest()[:24]
        self.version = "tt1:" + base64.urlsafe_b64encode(digest).decode("ascii")

    def count_text(self, text: str) -> int:
        return len(self._encoding.encode(text, disallowed_special=()))

    def count_messages(self, messages) -> int:
        return (
            sum(self.count_text(item.content) + self.message_overhead_tokens for item in messages)
            + self.request_overhead_tokens
        )


def token_counter_from_profile(profile: dict):
    """仅从冻结且经过校验的 Profile 字段构建预算计数器。"""
    from backend.application.model_profiles import validate_profile_config

    validate_profile_config({**profile, "status": "enabled", "is_default": False})
    tokenizer_config = profile["tokenizer_config"]
    if profile["tokenizer_kind"] == "mock":
        return MockTokenCounter(f"mock-tokenizer@{profile['tokenizer_version']}")
    return TikTokenCounter(
        tokenizer_config["encoding_name"],
        message_overhead_tokens=tokenizer_config["message_overhead_tokens"],
        request_overhead_tokens=tokenizer_config["request_overhead_tokens"],
        calibration_version=tokenizer_config["calibration_version"],
        profile_tokenizer_version=profile["tokenizer_version"],
    )
