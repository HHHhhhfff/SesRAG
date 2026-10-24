import hashlib
import math
from collections.abc import AsyncGenerator

from backend.domain.ports import ModelRequest


class MockEmbeddingProvider:
    """使用内容哈希生成稳定向量，保证离线测试不依赖外部模型。"""

    def __init__(self, dimension: int = 384) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [digest[index % len(digest)] / 255.0 for index in range(self.dimension)]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class MockModelProvider:
    """返回可重复的证据型回答增量。"""

    async def stream_answer(
        self, question: str, evidence: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        del question
        if evidence:
            answer = f"根据检索到的资料：{evidence[0].get('text', '')}"
        else:
            answer = "当前知识库没有足够证据回答这个问题。"
        for part in answer.split(" "):
            yield f"{part} "

    async def stream_request(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        """消费 schema 2 的已规划消息，不拼接隐藏提示或证据。"""
        question = next(
            (message.content for message in reversed(request.messages) if message.role == "user"),
            "",
        )
        evidence = [
            {"text": message.content}
            for message in request.messages
            if message.role == "system" and message.content.startswith("[非可信检索证据]")
        ]
        async for part in self.stream_answer(question, evidence):
            yield part
