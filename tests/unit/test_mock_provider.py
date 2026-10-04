import asyncio

from backend.infrastructure.providers.mock import MockEmbeddingProvider, MockModelProvider


def test_mock_embedding_is_deterministic_and_fixed_width():
    provider = MockEmbeddingProvider(dimension=8)

    assert provider.embed("same") == provider.embed("same")
    assert len(provider.embed("same")) == 8


def test_mock_model_streams_answer_deltas():
    async def collect() -> list[str]:
        provider = MockModelProvider()
        return [part async for part in provider.stream_answer("question", [{"text": "evidence"}])]

    parts = asyncio.run(collect())

    assert parts
    assert "evidence" in "".join(parts)
