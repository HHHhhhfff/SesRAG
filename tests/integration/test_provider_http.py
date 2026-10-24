"""真实本地 HTTP/SSE 服务验证 httpx 适配器，禁止依赖外部模型。"""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.application.errors import ApplicationError
from backend.domain.ports import ModelRequest, ModelRequestMessage
from backend.infrastructure.providers import openai_compatible as module


@pytest.fixture
def provider_server():
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            observed.append(payload)
            model = payload["model"]
            if model == "slowheaders":
                try:
                    self.wfile.write(b"HTTP/1.1 200 OK\r\n")
                    self.wfile.flush()
                    for _ in range(20):
                        if stop.wait(0.03):
                            break
                        self.wfile.write(b"X-Progress: yes\r\n")
                        self.wfile.flush()
                    self.wfile.write(b"\r\n")
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            status = (
                int(model[4:])
                if model.startswith("http")
                else 400
                if model in {"context", "large-error", "slow-error"}
                else 200
            )
            self.send_response(status)
            self.send_header(
                "Content-Type",
                "text/event-stream" if self.path.endswith("completions") else "application/json",
            )
            self.end_headers()
            try:
                if model == "context":
                    self.wfile.write(
                        b'{"error":{"code":"context_length_exceeded",'
                        b'"message":"secret prompt /private"}}'
                    )
                elif model == "large-error":
                    self.wfile.write(b"x" * 1024)
                elif model == "slow-error":
                    self.wfile.flush()
                    stop.wait(2)
                    self.wfile.write(b"error")
                elif status != 200:
                    self.wfile.write(b"secret upstream body /host/path")
                elif model == "broken":
                    self.wfile.write(b"not json\n")
                elif model == "timeout":
                    stop.wait(2)
                elif self.path.endswith("embeddings"):
                    self.wfile.write(json.dumps({"data": [{"embedding": [0.5] * 384}]}).encode())
                else:
                    values = ["one", "two", "three"] if model != "empty" else [""]
                    for value in values:
                        event = {"choices": [{"delta": {"content": value}}]}
                        self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
                        self.wfile.flush()
                    self.wfile.write(b"data: [DONE]\n\n")
            except (BrokenPipeError, ConnectionResetError):
                pass

    stop = threading.Event()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1", observed
    stop.set()
    server.shutdown()
    server.server_close()
    thread.join(3)


@pytest.mark.asyncio
async def test_real_local_http_stream_and_embedding(provider_server):
    url, observed = provider_server
    provider = module.OpenAICompatibleProvider(url, "private-key", "valid", "valid")
    assert await provider.embed("question") == [0.5] * 384
    # Worker 每片使用不同 guarded Task，HTTP 流必须支持跨 Task 恢复迭代。
    stream = provider.stream_answer("question", [])
    assert await asyncio.create_task(anext(stream)) == "one"
    assert await asyncio.create_task(anext(stream)) == "two"
    assert await asyncio.create_task(anext(stream)) == "three"
    with pytest.raises(StopAsyncIteration):
        await asyncio.create_task(anext(stream))
    assert observed[1]["stream"] is True


@pytest.mark.asyncio
async def test_model_request_sends_only_planned_roles_model_and_output_limit(provider_server):
    url, observed = provider_server
    provider = module.OpenAICompatibleProvider(url, "private-key", "selected-model", "embedding")
    request = ModelRequest(
        messages=(ModelRequestMessage("system", "safe"), ModelRequestMessage("user", "question")),
        max_output_tokens=77,
        selected_evidence=(("doc-1", "chunk-1"),),
        generation_params={"temperature": 0.2},
    )
    assert [part async for part in provider.stream_request(request)] == ["one", "two", "three"]
    payload = observed[0]
    assert payload["model"] == "selected-model"
    assert payload["messages"] == [
        {"role": "system", "content": "safe"},
        {"role": "user", "content": "question"},
    ]
    assert payload["max_tokens"] == 77 and payload["temperature"] == 0.2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model,code,retryable",
    [
        ("http400", "PROVIDER_HTTP_400", False),
        ("http401", "PROVIDER_HTTP_401", False),
        ("http403", "PROVIDER_HTTP_403", False),
        ("http429", "PROVIDER_HTTP_429", True),
        ("http503", "PROVIDER_HTTP_503", True),
        ("broken", "PROVIDER_INVALID_RESPONSE", False),
        ("empty", "PROVIDER_EMPTY_CONTENT", False),
        ("timeout", "PROVIDER_TIMEOUT", True),
    ],
)
async def test_local_http_protocol_failures(provider_server, monkeypatch, model, code, retryable):
    url, _ = provider_server
    monkeypatch.setattr(module, "PROVIDER_TIMEOUT", 0.75)
    provider = module.OpenAICompatibleProvider(url, "private-key", model, model)
    with pytest.raises(ApplicationError) as error:
        _ = [part async for part in provider.stream_answer("private-question", [])]
    assert error.value.code == code and error.value.retryable is retryable
    assert all(
        value not in str(error.value) for value in ("private-key", "private-question", "/host/path")
    )


async def test_total_budget_covers_incremental_response_headers(provider_server, monkeypatch):
    url, _ = provider_server
    monkeypatch.setattr(module, "PROVIDER_TIMEOUT", 0.15)
    provider = module.OpenAICompatibleProvider(url, "private-key", "slowheaders", "slowheaders")
    started = asyncio.get_running_loop().time()
    with pytest.raises(ApplicationError) as error:
        await provider.embed("question")
    assert error.value.code == "PROVIDER_TIMEOUT"
    assert asyncio.get_running_loop().time() - started < 0.5


@pytest.mark.asyncio
async def test_upstream_context_limit_is_safe_permanent_context_error(provider_server):
    url, _ = provider_server
    provider = module.OpenAICompatibleProvider(url, "private-key", "context", "embedding")
    with pytest.raises(ApplicationError) as error:
        _ = [part async for part in provider.stream_answer("private-question", [])]
    assert error.value.code == "CONTEXT_TOO_LARGE" and not error.value.retryable
    assert "private" not in str(error.value) and "secret prompt" not in str(error.value)


@pytest.mark.parametrize(
    "model,code", [("large-error", "PROVIDER_RESPONSE_LIMIT"), ("slow-error", "PROVIDER_TIMEOUT")]
)
async def test_error_response_body_obeys_same_size_and_absolute_deadline(
    provider_server, monkeypatch, model, code
):
    # 错误HTTP响应也不得先aread完整正文，再做体积和总时长限制。
    url, _ = provider_server
    monkeypatch.setattr(module, "MAX_RESPONSE_BYTES", 128)
    monkeypatch.setattr(module, "PROVIDER_TIMEOUT", 0.2)
    provider = module.OpenAICompatibleProvider(url, "private-key", model, model)
    started = asyncio.get_running_loop().time()
    with pytest.raises(ApplicationError) as error:
        await provider.embed("question")
    assert error.value.code == code
    assert asyncio.get_running_loop().time() - started < 1
