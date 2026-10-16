from backend.application.errors import PermanentTaskError
from backend.domain.ports import EmbeddingPort, ModelProvider
from backend.infrastructure.providers.mock import MockEmbeddingProvider, MockModelProvider
from backend.infrastructure.providers.openai_compatible import OpenAICompatibleProvider


def providers_for_snapshot(
    snapshot: dict, api_key: str | None
) -> tuple[EmbeddingPort, ModelProvider]:
    if snapshot["mock_provider"]:
        return MockEmbeddingProvider(384), MockModelProvider()
    if not api_key:
        raise PermanentTaskError("INVALID_RUN_SNAPSHOT", "真实模型凭据未配置")
    provider = OpenAICompatibleProvider(
        snapshot["base_url"], api_key, snapshot["model"], snapshot["embedding_model"]
    )
    return provider, provider
