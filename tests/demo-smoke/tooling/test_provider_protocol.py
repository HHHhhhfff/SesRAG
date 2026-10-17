"""工具负哨兵：token越界及原始泄漏必须在报告脱敏前失败。"""

import asyncio
import json
import time
import unittest

from provider_protocol import ProtocolServer, assert_safe_raw, validate_token


class Guards(unittest.TestCase):
    def test_token_rejects_path_and_unknown_scope(self):
        self.assertEqual(validate_token("a1b2c3d4"), "a1b2c3d4")
        for token in ("", "../other", "A1B2C3D4", "a1b2c3d4/next"):
            with self.assertRaises(ValueError):
                validate_token(token)

    def test_raw_leak_rejected_before_any_redaction(self):
        self.assertTrue(assert_safe_raw([{"error": "安全失败"}], ["virtual-secret"]))
        for value in ("virtual-secret", {"nested": ["virtual-secret"]}):
            with self.assertRaises(AssertionError):
                assert_safe_raw([value], ["virtual-secret"])


class SocketLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_endpoint_cannot_receive_success_fixture(self):
        server = ProtocolServer("a1b2c3d4")
        async with server.serve():
            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            body = b'{"model":"test"}'
            writer.write(
                (
                    "POST /a1b2c3d4/v1/unknown HTTP/1.1\r\nHost: localhost\r\n"
                    f"Content-Length: {len(body)}\r\n\r\n"
                ).encode()
                + body
            )
            await writer.drain()
            reply = await reader.read()
            writer.close()
            await writer.wait_closed()
            self.assertIn(b"404", reply.split(b"\r\n")[0])
            self.assertEqual(server.calls, [])

    async def test_unknown_token_does_not_consume_scenario_and_listener_closes(self):
        server = ProtocolServer("a1b2c3d4")
        async with server.serve():
            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            body = json.dumps({"model": "test", "input": "safe"}).encode()
            writer.write(
                (
                    "POST /deadbeef/v1/embeddings HTTP/1.1\r\nHost: localhost\r\n"
                    f"Content-Length: {len(body)}\r\n\r\n"
                ).encode()
                + body
            )
            await writer.drain()
            reply = await reader.read()
            writer.close()
            await writer.wait_closed()
            self.assertIn(b"404", reply.split(b"\r\n")[0])
            self.assertEqual(server.calls, [])
        self.assertTrue(server.closed)
        with self.assertRaises(OSError):
            await asyncio.open_connection("127.0.0.1", server.port)

    async def test_exception_body_closes_active_hanging_connection(self):
        server = ProtocolServer("a1b2c3d4", mode="timeout")
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, "验证体异常"):
            async with server.serve():
                reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
                body = b'{"model":"test","input":"safe"}'
                writer.write(
                    (
                        "POST /a1b2c3d4/v1/embeddings HTTP/1.1\r\nHost: localhost\r\n"
                        f"Content-Length: {len(body)}\r\n\r\n"
                    ).encode()
                    + body
                )
                await writer.drain()
                async with asyncio.timeout(2):
                    while not server.calls:
                        await asyncio.sleep(0.01)
                raise RuntimeError("验证体异常")
        self.assertTrue(server.closed)
        self.assertLess(time.monotonic() - started, 2, "异常finally不能等待协议20秒预算才关闭")
        self.assertEqual(await reader.read(), b"")
        writer.close()
        await writer.wait_closed()


if __name__ == "__main__":
    unittest.main()
