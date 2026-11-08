"""从冻结配置重建 Embedding／rerank，不读取生成模型的可变默认值。"""

import os

from backend.application.errors import PermanentTaskError
from backend.application.vector_validation import normalize_l2_float32, validate_vector
from backend.domain.rag_profiles import EmbeddingConfig, RerankConfig
from backend.infrastructure.providers.mock import MockEmbeddingProvider


def resolve_rag_secret(alias):
    if alias not in {"env:RAG_EMBEDDING_API_KEY", "env:RAG_RERANK_API_KEY"}:
        raise PermanentTaskError("MODEL_CREDENTIAL_UNAVAILABLE", "凭据引用不受信")
    value = os.getenv(alias.removeprefix("env:"))
    if not value:
        raise PermanentTaskError("MODEL_CREDENTIAL_UNAVAILABLE", "模型凭据未配置")
    return value


class MockEmbeddingV2:
    def __init__(self, dimension, normalization="none"):
        self.dimension = dimension
        self.normalization = normalization

    async def embed(self, texts, *, purpose="document"):
        provider = MockEmbeddingProvider(self.dimension)
        convert = normalize_l2_float32 if self.normalization == "l2_float32_v1" else validate_vector
        return tuple(convert(provider.embed(text), dimension=self.dimension) for text in texts)


class MockRerank:
    async def rank(self, query, texts):
        # 明确仅供工程验证的词集合交集，不能当真实语义重排验收。
        terms = set(query.casefold().split())
        return tuple(
            sorted(
                (
                    (i, len(terms & set(t.casefold().split())) / max(1, len(terms)))
                    for i, t in enumerate(texts)
                ),
                key=lambda p: (-p[1], p[0]),
            )
        )


def embedding_from_profile(snapshot, *, transport=None):
    config = EmbeddingConfig.model_validate(
        snapshot["config"] if "config" in snapshot else snapshot
    )
    if config.adapter_kind == "mock":
        return MockEmbeddingV2(config.space.dimension, config.space.normalization)
    if config.counter_status != "verified":
        raise PermanentTaskError("INPUT_COUNTER_UNVERIFIED", "真实向量计数条件未核实")
    from backend.infrastructure.providers.bailian_embedding import BailianEmbedding

    return BailianEmbedding(config, resolve_rag_secret(config.config_ref), transport=transport)


def rerank_from_profile(snapshot, *, transport=None):
    config = RerankConfig.model_validate(snapshot["config"] if "config" in snapshot else snapshot)
    if config.adapter_kind == "mock":
        return MockRerank()
    if config.counter_status != "verified":
        raise PermanentTaskError("INPUT_COUNTER_UNVERIFIED", "真实重排计数条件未核实")
    from backend.infrastructure.providers.bailian_rerank import BailianRerank

    return BailianRerank(config, resolve_rag_secret(config.config_ref), transport=transport)
