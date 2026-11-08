"""百炼兼容Embedding端点；dimensions显式传入并逐项恢复index。"""

from urllib.parse import urlsplit

from backend.application.errors import PermanentTaskError, TransientTaskError
from backend.application.vector_validation import normalize_l2_float32, validate_vector
from backend.infrastructure.rag.download_safety import SafeHTTP, decode_json


class BailianEmbedding:
    def __init__(self, config, secret, *, transport=None):
        self.config, self.secret = config, secret
        self.http = SafeHTTP([urlsplit(config.base_url).hostname], transport=transport)

    async def embed(self, texts, *, purpose="document"):
        config = self.config
        if not 1 <= len(texts) <= config.batch_size or any(
            not t.strip() or len(t.encode()) > config.max_input_bytes for t in texts
        ):
            raise PermanentTaskError("EMBEDDING_INPUT_LIMIT", "向量输入超过冻结预算")
        status, raw = await self.http.request(
            "POST",
            config.base_url.rstrip("/") + "/embeddings",
            headers={"Authorization": f"Bearer {self.secret}"},
            json_body={
                "model": config.space.model,
                "input": list(texts),
                "dimensions": config.space.dimension,
                "encoding_format": "float",
            },
        )
        if status in {429, 500, 502, 503, 504}:
            raise TransientTaskError("EMBEDDING_TEMPORARY_UNAVAILABLE", "向量服务暂不可用")
        if status != 200:
            raise PermanentTaskError("EMBEDDING_SERVICE_FAILED", "向量服务拒绝请求")
        body = decode_json(raw, "EMBEDDING_PROTOCOL_INVALID")
        try:
            rows = body["data"]
            if (
                any(type(row["index"]) is not int for row in rows)
                or len(rows) != len(texts)
                or sorted(row["index"] for row in rows) != list(range(len(texts)))
            ):
                raise ValueError()
            vectors = tuple(
                validate_vector(row["embedding"], dimension=config.space.dimension)
                for row in sorted(rows, key=lambda r: r["index"])
            )
            if config.space.normalization == "l2_float32_v1":
                vectors = tuple(
                    normalize_l2_float32(vector, dimension=config.space.dimension)
                    for vector in vectors
                )
            return vectors
        except (KeyError, TypeError, ValueError):
            raise PermanentTaskError(
                "EMBEDDING_PROTOCOL_INVALID", "向量返回身份或数量无效"
            ) from None
