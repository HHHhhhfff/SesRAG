import asyncio
import json
from collections.abc import AsyncGenerator

import httpx

from backend.application.errors import PermanentTaskError, TransientTaskError
from backend.application.vector_validation import validate_vector
from backend.domain.ports import ModelRequest

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PROVIDER_TIMEOUT = 60


def check_status(status: int, body: bytes = b"") -> None:
    if 200 <= status < 300:
        return
    folded = body[:MAX_RESPONSE_BYTES].decode("utf-8", errors="ignore").casefold()
    if "context_length" in folded or "maximum context length" in folded:
        raise PermanentTaskError("CONTEXT_TOO_LARGE", "模型上下文超出配置窗口")
    error = TransientTaskError if status in (408, 429) or status >= 500 else PermanentTaskError
    raise error(f"PROVIDER_HTTP_{status}", "模型服务请求失败")


class OpenAICompatibleProvider:
    """有界 HTTP/SSE 适配器；上游响应及凭据不进入公开异常。"""

    def __init__(self, base_url: str, api_key: str, model: str, embedding_model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model

    async def _bytes(self, endpoint, payload):
        try:
            # generator 的每个 anext 可在不同 Task 中执行；预算不跨 yield 绑定某个 Task。
            deadline = asyncio.get_running_loop().time() + PROVIDER_TIMEOUT
            async with httpx.AsyncClient(timeout=30) as client:
                request = client.build_request(
                    "POST",
                    f"{self.base_url}/{endpoint}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                remaining = deadline - asyncio.get_running_loop().time()
                response = await asyncio.wait_for(
                    client.send(request, stream=True), max(0, remaining)
                )
                try:
                    error_body = bytearray()
                    count = 0
                    iterator = response.aiter_bytes()
                    while True:
                        remaining = deadline - asyncio.get_running_loop().time()
                        if remaining <= 0:
                            raise TimeoutError()
                        try:
                            chunk = await asyncio.wait_for(anext(iterator), remaining)
                        except StopAsyncIteration:
                            break
                        count += len(chunk)
                        if count > MAX_RESPONSE_BYTES:
                            raise PermanentTaskError("PROVIDER_RESPONSE_LIMIT", "模型响应超过限制")
                        if response.status_code >= 400:
                            # 错误正文与成功流共用字节/总时长限制，避免aread无界分配。
                            error_body.extend(chunk)
                        else:
                            check_status(response.status_code)
                            yield chunk
                    check_status(response.status_code, bytes(error_body))
                finally:
                    await response.aclose()
        except (TimeoutError, httpx.TimeoutException):
            raise TransientTaskError("PROVIDER_TIMEOUT", "模型服务超时") from None
        except httpx.TransportError:
            raise TransientTaskError("PROVIDER_TRANSPORT_ERROR", "模型服务连接失败") from None

    async def embed(self, text: str) -> list[float]:
        body = b"".join(
            [
                chunk
                async for chunk in self._bytes(
                    "embeddings", {"model": self.embedding_model, "input": text}
                )
            ]
        )
        try:
            vector = json.loads(body)["data"][0]["embedding"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise PermanentTaskError("PROVIDER_INVALID_RESPONSE", "模型响应格式无效") from None
        return validate_vector(vector)

    async def stream_answer(
        self, question: str, evidence: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        prompt = "\n".join(item.get("text", "") for item in evidence)
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [
                {"role": "system", "content": "只根据给定证据回答。"},
                {"role": "user", "content": f"问题：{question}\n证据：{prompt}"},
            ],
        }
        pending = b""
        content = False
        completed = False
        stream = self._bytes("chat/completions", payload)
        try:
            async for chunk in stream:
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    line = line.rstrip(b"\r")
                    if not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if data == b"[DONE]":
                        completed = True
                        break
                    try:
                        choices = json.loads(data)["choices"]
                        if not choices:
                            continue
                        delta = choices[0]["delta"].get("content")
                        if delta is None:
                            continue
                        if not isinstance(delta, str):
                            raise ValueError()
                    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                        raise PermanentTaskError(
                            "PROVIDER_INVALID_RESPONSE", "模型响应格式无效"
                        ) from None
                    if delta:
                        content = content or bool(delta.strip())
                        yield delta
                if completed:
                    break
        finally:
            await stream.aclose()
        if not completed:
            raise PermanentTaskError("PROVIDER_INVALID_RESPONSE", "模型流未正常结束")
        if not content:
            raise PermanentTaskError("PROVIDER_EMPTY_CONTENT", "模型没有返回有效内容")

    async def stream_request(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        """只发送 ContextPlan 已选内容及冻结的模型输出参数。"""
        if request.max_output_tokens <= 0:
            raise PermanentTaskError("INVALID_RUN_SNAPSHOT", "模型输出预算无效")
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "max_tokens": request.max_output_tokens,
            **request.generation_params,
        }
        pending = b""
        content = False
        completed = False
        stream = self._bytes("chat/completions", payload)
        try:
            async for chunk in stream:
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    line = line.rstrip(b"\r")
                    if not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if data == b"[DONE]":
                        completed = True
                        break
                    try:
                        choices = json.loads(data)["choices"]
                        delta = choices[0]["delta"].get("content") if choices else None
                        if delta is not None and not isinstance(delta, str):
                            raise ValueError()
                    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                        raise PermanentTaskError(
                            "PROVIDER_INVALID_RESPONSE", "模型响应格式无效"
                        ) from None
                    if delta:
                        content = content or bool(delta.strip())
                        yield delta
                if completed:
                    break
        finally:
            await stream.aclose()
        if not completed:
            raise PermanentTaskError("PROVIDER_INVALID_RESPONSE", "模型流未正常结束")
        if not content:
            raise PermanentTaskError("PROVIDER_EMPTY_CONTENT", "模型没有返回有效内容")
