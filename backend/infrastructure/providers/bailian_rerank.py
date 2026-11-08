"""百炼原生rerank；只接受原候选index，不跨请求混合分数。"""

import math
from urllib.parse import urlsplit

from backend.application.errors import PermanentTaskError, TransientTaskError
from backend.infrastructure.rag.download_safety import SafeHTTP, decode_json


def utf8_prefix(text, limit):
    return text.encode()[:limit].decode("utf-8", errors="ignore")


class BailianRerank:
    def __init__(self, config, secret, *, transport=None):
        self.config, self.secret = config, secret
        self.http = SafeHTTP([urlsplit(config.endpoint).hostname], transport=transport)

    async def rank(self, query, texts):
        c = self.config
        if not texts:
            return ()
        if len(query.encode()) > c.max_query_bytes:
            raise PermanentTaskError("RERANK_INPUT_BUDGET_EXCEEDED", "重排问题超过预算")
        per_document = min(
            c.max_document_bytes,
            (c.max_request_bytes - len(query.encode()) * len(texts)) // len(texts),
        )
        if per_document < 4:
            raise PermanentTaskError("RERANK_INPUT_BUDGET_EXCEEDED", "重排请求预算不足")
        documents = [utf8_prefix(t, per_document) for t in texts]
        self.input_ranges = tuple((0, len(value)) for value in documents)
        if any(not t.strip() for t in documents):
            raise PermanentTaskError("RERANK_INPUT_BUDGET_EXCEEDED", "重排候选没有有效文本")
        status, raw = await self.http.request(
            "POST",
            c.endpoint,
            headers={"Authorization": f"Bearer {self.secret}"},
            json_body={
                "model": c.model,
                "input": {"query": query, "documents": documents},
                "parameters": {"top_n": len(documents)},
            },
        )
        if status in {429, 500, 502, 503, 504}:
            raise TransientTaskError("RERANK_TEMPORARY_UNAVAILABLE", "重排服务暂不可用")
        if status in {401, 403}:
            raise PermanentTaskError("RERANK_AUTH_FAILED", "重排认证或权限失败")
        if status != 200:
            raise PermanentTaskError("RERANK_SERVICE_FAILED", "重排服务拒绝请求")
        body = decode_json(raw, "RERANK_PROTOCOL_INVALID")
        try:
            rows = body["output"]["results"]
            if len(rows) != len(texts) or sorted(r["index"] for r in rows) != list(
                range(len(texts))
            ):
                raise ValueError()
            result = tuple((r["index"], r["relevance_score"]) for r in rows)
            if any(
                type(i) is not int
                or type(v) not in {int, float}
                or not math.isfinite(v)
                or not 0 <= v <= 1
                for i, v in result
            ):
                raise ValueError()
            return tuple(sorted(result, key=lambda p: (-p[1], p[0])))
        except (KeyError, TypeError, ValueError):
            raise PermanentTaskError("RERANK_PROTOCOL_INVALID", "重排候选身份或分数无效") from None
