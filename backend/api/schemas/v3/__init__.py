"""v3 公开契约；禁止任意额外字段和内部凭据投影。"""

from backend.domain.rag import StrictModel

__all__ = ["StrictModel"]
