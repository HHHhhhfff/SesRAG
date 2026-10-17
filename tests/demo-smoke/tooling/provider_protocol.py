"""本地协议fixture与脱敏前哨兵检查；不保存请求正文或Authorization。"""

import asyncio
import json
import re
import time
from contextlib import asynccontextmanager


def validate_token(token):
    if not isinstance(token, str) or not re.fullmatch("[a-f0-9]{8}", token):
        raise ValueError("协议场景token无效")
    return token


def assert_safe_raw(values, sentinels):
    raw = json.dumps(values, ensure_ascii=False, default=str)
    assert all(value not in raw for value in sentinels), "产品原始输出出现合成敏感哨兵"
    return True


class ProtocolServer:
    """真实TCP HTTP/1.1；按随机token配置，控制对象不解析Prompt触发词。"""

    def __init__(self, token, *, endpoint="embeddings", mode="valid", gate=None):
        self.token = validate_token(token)
        self.endpoint, self.mode, self.gate = endpoint, mode, gate
        self.calls, self.fragments, self.tasks, self.writers = [], [], set(), set()
        self.finished = False
        self.closed = False

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        self.writers.add(writer)
        try:
            async with asyncio.timeout(20):
                head = await reader.readuntil(b"\r\n\r\n")
                lines = head.decode("ascii").split("\r\n")
                method, target, _ = lines[0].split(" ")
                headers = dict(line.split(": ", 1) for line in lines[1:] if ": " in line)
                length = int(
                    next((v for k, v in headers.items() if k.lower() == "content-length"), "0")
                )
                assert 0 < length < 2 * 1024 * 1024
                body = json.loads(await reader.readexactly(length))
                prefix = "/" + self.token + "/v1/"
                if method != "POST" or not target.startswith(prefix):
                    await self.respond(writer, 404, b"unknown scenario")
                    return
                endpoint = target.removeprefix(prefix)
                if endpoint not in ("embeddings", "chat/completions"):
                    await self.respond(writer, 404, b"unknown endpoint")
                    return
                self.calls.append(
                    {
                        "endpoint": endpoint,
                        "model": body.get("model"),
                        "stream": body.get("stream"),
                        "at": time.monotonic(),
                    }
                )
                mode = self.mode if endpoint == self.endpoint else "valid"
                if mode.startswith("status-"):
                    await self.respond(
                        writer,
                        int(mode.removeprefix("status-")),
                        b"upstream-body-5b virtual-secret-5b credential-5b host-private-5b",
                    )
                elif mode == "socket":
                    writer.transport.abort()
                elif mode == "timeout":
                    # 生产适配器测试预算缩短；实际网络连接保持未返回，绝不抛伪HTTPError。
                    await reader.read()
                elif endpoint == "embeddings":
                    await self.respond(writer, 200, embedding_fixture(mode))
                else:
                    await self.stream(writer, mode)
        except (ConnectionError, asyncio.IncompleteReadError, TimeoutError):
            pass
        finally:
            self.tasks.discard(task)
            self.writers.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    async def respond(self, writer, status, body):
        writer.write(
            (
                f"HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
            ).encode()
            + body
        )
        await writer.drain()

    async def stream(self, writer, mode):
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
            b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n"
        )
        frames = chat_fixture(mode)
        for index, frame in enumerate(frames):
            writer.write(f"{len(frame):x}\r\n".encode() + frame + b"\r\n")
            await writer.drain()
            self.fragments.append({"index": index, "at": time.monotonic()})
            if mode == "three" and index < 3:
                await self.gate(index)
        writer.write(b"0\r\n\r\n")
        await writer.drain()
        self.finished = True

    @asynccontextmanager
    async def serve(self):
        server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        self.listener = server
        address = server.sockets[0].getsockname()
        self.port = address[1]
        try:
            yield f"http://127.0.0.1:{self.port}/{self.token}/v1"
        finally:
            server.close()
            for writer in list(self.writers):
                writer.close()
            pending = list(self.tasks)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            await server.wait_closed()
            self.closed = not server.is_serving() and not self.tasks and not self.writers
            assert self.closed, "协议listener/连接/协程未完全关闭"


def embedding_fixture(mode):
    if mode == "non-json":
        return b"upstream-body-5b"
    if mode == "missing":
        value = {}
    elif mode == "empty":
        value = {"data": []}
    elif mode == "wrong-data":
        value = {"data": "bad"}
    elif mode == "missing-embedding":
        value = {"data": [{}]}
    else:
        vector = [1.0] + [0.0] * 383
        if mode in ("383", "385"):
            vector = [0.0] * int(mode)
        elif mode == "wrong-vector":
            vector = "bad"
        elif mode in ("non-numeric", "non-finite", "boolean", "huge"):
            vector[0] = {
                "non-numeric": "bad",
                "non-finite": float("nan"),
                "boolean": True,
                "huge": 1e100,
            }[mode]
        value = {"data": [{"embedding": vector}]}
    return json.dumps(value).encode()


def chat_fixture(mode):
    def data(value):
        return ("data: " + json.dumps(value, ensure_ascii=False) + "\n\n").encode()

    done = b"data: [DONE]\n\n"

    def valid(text):
        return data({"choices": [{"delta": {"content": text}}]})

    if mode == "three":
        return [valid("第一片"), valid("第二片"), valid("第三片"), done]
    if mode == "non-json":
        return [b"data: upstream-body-5b\n\n", done]
    if mode == "missing":
        return [data({}), done]
    if mode == "empty":
        return [data({"choices": []}), done]
    if mode == "wrong-choices":
        return [data({"choices": 1}), done]
    if mode == "wrong-delta":
        return [data({"choices": [{"delta": 1}]}), done]
    if mode == "wrong-content":
        return [data({"choices": [{"delta": {"content": 1}}]}), done]
    if mode == "missing-content":
        return [data({"choices": [{"delta": {}}]}), done]
    if mode == "empty-content":
        return [valid(" "), done]
    if mode == "missing-done":
        return [valid("安全片段")]
    return [valid("安全回答"), done]
