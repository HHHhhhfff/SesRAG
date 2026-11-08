"""真实适配器的受控协议测试；不读取凭据或访问外网。"""

import json
import math

import httpx
import pytest

from backend.application.errors import ApplicationError
from backend.domain.rag_profiles import EmbeddingConfig, RerankConfig
from backend.infrastructure.providers.bailian_embedding import BailianEmbedding
from backend.infrastructure.providers.bailian_rerank import BailianRerank


@pytest.mark.asyncio
async def test_embedding_explicit_dimension_and_response_index_order():
    def handle(request):
        data = json.loads(request.content)
        assert request.url.path == "/compatible-mode/v1/embeddings"
        assert data["dimensions"] == 1024 and data["encoding_format"] == "float"
        assert "text_type" not in data and "input_type" not in data
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.2] * 1024},
                    {"index": 0, "embedding": [0.1] * 1024},
                ]
            },
        )

    config = EmbeddingConfig(
        adapter_kind="bailian",
        space={
            "provider": "bailian",
            "model": "qwen3.7-text-embedding",
            "revision": "test",
            "dimension": 1024,
            "normalization": "l2_float32_v1",
        },
        base_url="https://example.com/compatible-mode/v1",
        config_ref="env:RAG_EMBEDDING_API_KEY",
    )
    result = await BailianEmbedding(
        config, "test-only", transport=httpx.MockTransport(handle)
    ).embed(("a", "b"))
    assert math.isclose(math.hypot(*result[0]), 1, abs_tol=1e-6)
    assert math.isclose(math.hypot(*result[1]), 1, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_rerank_uses_native_endpoint_and_rejects_duplicate_identity():
    def handle(request):
        data = json.loads(request.content)
        assert request.url.path == "/api/v1/services/rerank/text-rerank/text-rerank"
        assert data["parameters"] == {"top_n": 2}
        return httpx.Response(
            200,
            json={
                "output": {
                    "results": [
                        {"index": 0, "relevance_score": 0.7},
                        {"index": 0, "relevance_score": 0.3},
                    ]
                }
            },
        )

    config = RerankConfig(
        adapter_kind="bailian",
        endpoint="https://example.com/api/v1/services/rerank/text-rerank/text-rerank",
        config_ref="env:RAG_RERANK_API_KEY",
    )
    with pytest.raises(ApplicationError) as error:
        await BailianRerank(config, "test-only", transport=httpx.MockTransport(handle)).rank(
            "query", ("a", "b")
        )
    assert error.value.code == "RERANK_PROTOCOL_INVALID"


@pytest.mark.parametrize("status", [401, 403])
async def test_rerank_authentication_failure_cannot_masquerade_as_service_fallback(status):
    # RAG-028：错误凭据/权限不是可隐藏为dense降级的服务故障。
    config = RerankConfig(
        adapter_kind="bailian",
        endpoint="https://example.com/api/v1/services/rerank/text-rerank/text-rerank",
        config_ref="env:RAG_RERANK_API_KEY",
    )
    with pytest.raises(ApplicationError) as error:
        await BailianRerank(
            config,
            "test-only",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status, json={"private_error": "do not expose"})
            ),
        ).rank("query", ("text",))
    assert error.value.code == "RERANK_AUTH_FAILED"
