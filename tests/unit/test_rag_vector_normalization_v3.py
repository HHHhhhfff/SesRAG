"""真实新空间须固定L2/float32语义，不能仅改变空间标签。"""

import math
import struct

import httpx
import pytest

from backend.domain.rag_profiles import EmbeddingConfig
from backend.infrastructure.providers.bailian_embedding import BailianEmbedding


@pytest.mark.asyncio
async def test_bailian_normalization_is_identical_for_query_and_documents():
    config = EmbeddingConfig(
        adapter_kind="bailian",
        base_url="https://example.com/compatible-mode/v1",
        config_ref="env:RAG_EMBEDDING_API_KEY",
        space={
            "provider": "bailian",
            "model": "qwen3.7-text-embedding",
            "revision": "test",
            "dimension": 1024,
            "normalization": "l2_float32_v1",
        },
    )
    raw = [3.0, 4.0, *([0.0] * 1022)]

    def handle(_request):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": raw}]})

    adapter = BailianEmbedding(config, "test-only", transport=httpx.MockTransport(handle))
    document = await adapter.embed(("document",))
    query = await adapter.embed(("query",), purpose="query")
    assert document == query
    assert math.isclose(math.hypot(*document[0]), 1, abs_tol=1e-6)
    assert document[0][0] == struct.unpack("<f", struct.pack("<f", 0.6))[0]
