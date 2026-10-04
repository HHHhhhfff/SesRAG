from collections.abc import AsyncIterator

import httpx


class OpenAICompatibleProvider:
    """最小 OpenAI-compatible 适配器；不在领域层暴露厂商 SDK。"""

    def __init__(self, base_url: str, api_key: str, model: str, embedding_model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.embedding_model, "input": text},
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

    async def stream_answer(
        self, question: str, evidence: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        prompt = "\n".join(item.get("text", "") for item in evidence)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": "只根据给定证据回答。"},
                        {"role": "user", "content": f"问题：{question}\n证据：{prompt}"},
                    ],
                },
            )
            response.raise_for_status()
            yield response.json()["choices"][0]["message"]["content"]
