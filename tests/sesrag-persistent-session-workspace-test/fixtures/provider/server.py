"""测试环境用的有界 OpenAI-compatible Provider；不保存完整提示或认证值。"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import sys
import threading
import time
import uuid
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

MAX_INFERENCE_BODY_BYTES = 2 * 1024 * 1024
MAX_CONTROL_BODY_BYTES = 9 * 1024 * 1024


def observation_limit(value: str) -> int:
    limit = int(value)
    if not 1 <= limit <= 2000:
        raise ValueError("provider observation limit outside 1..2000")
    return limit


MAX_OBSERVATIONS = observation_limit(os.environ.get("PROVIDER_OBSERVATION_LIMIT", "100"))
MAX_OBSERVATION_BYTES = 8 * 1024 * 1024
MAX_CHUNKS = 8_192
MAX_CHUNK_BYTES = 65_536
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_EMBEDDING_BATCH = 256
MAX_MESSAGE_SUMMARIES = 512
MAX_SCENARIOS = 64
MAX_ACTIVE_REQUESTS = 32
MAX_DELAY_MS = 2_000
MAX_STALL_MS = 180_000
ALLOWED_SCENARIOS = {
    "normal",
    "slow",
    "stall",
    "empty",
    "malformed",
    "disconnect",
    "context-limit",
    "http-error",
    "partial-disconnect",
}
ALLOWED_PHASES = {"received", "first_delta", "waiting_release", "finished"}
MODEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SENTINEL_PATTERN = re.compile(r"(?:HISTORY|EVIDENCE|BATCH)-[A-Z0-9-]{4,48}")
DEFAULT_CHUNKS = ("受控 Provider ", "返回合成", "结果。")


def _error(code: str, message: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code}}
    if message:
        body["error"]["message"] = message
    return body


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _default_chunks(kind: str) -> list[str]:
    if kind == "slow":
        return ["slow-", "stream-", "fixture"]
    return list(DEFAULT_CHUNKS)


def _chunk_packet(content: str) -> dict[str, Any]:
    return {
        "id": "fixture-completion",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
    }


def _encoded_frame(data: bytes) -> bytes:
    return b"data: " + data + b"\n\n"


def _response_size(chunks: list[str]) -> int:
    size = sum(len(_encoded_frame(_json_bytes(_chunk_packet(chunk)))) for chunk in chunks)
    finish = {
        "id": "fixture-completion",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    return size + len(_encoded_frame(_json_bytes(finish))) + len(b"data: [DONE]\n\n")


def _valid_model(value: Any) -> bool:
    return isinstance(value, str) and MODEL_PATTERN.fullmatch(value) is not None


def _validated_scenario(body: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if body.get("schema_version") != 1 or type(body.get("schema_version")) is not int:
        return None, "scenario_version_unsupported"
    allowed_keys = {
        "schema_version",
        "model",
        "kind",
        "chunks",
        "chunk_delay_ms",
        "stall_after_chunk",
        "stall_timeout_ms",
        "http_status",
        "request_seq",
    }
    if set(body) - allowed_keys or not _valid_model(body.get("model")):
        return None, "scenario_invalid"
    kind = body.get("kind")
    if kind == "stall-after-first-delta":
        kind = "stall"
    if not isinstance(kind, str) or kind not in ALLOWED_SCENARIOS:
        return None, "scenario_invalid"

    chunks = body.get("chunks", _default_chunks(kind))
    if (
        not isinstance(chunks, list)
        or not chunks
        or len(chunks) > MAX_CHUNKS
        or any(
            not isinstance(chunk, str) or len(chunk.encode("utf-8")) > MAX_CHUNK_BYTES
            for chunk in chunks
        )
    ):
        return None, "scenario_invalid"

    delay_ms = body.get("chunk_delay_ms", 250 if kind == "slow" else 0)
    stall_after = body.get("stall_after_chunk", 1 if kind == "stall" else None)
    stall_timeout_ms = body.get("stall_timeout_ms", MAX_STALL_MS)
    http_status = body.get("http_status", 503)
    request_seq = body.get("request_seq")
    if type(delay_ms) is not int or not 0 <= delay_ms <= MAX_DELAY_MS:
        return None, "scenario_invalid"
    if type(stall_timeout_ms) is not int or not 0 <= stall_timeout_ms <= MAX_STALL_MS:
        return None, "scenario_invalid"
    if kind == "stall":
        if type(stall_after) is not int or not 1 <= stall_after <= len(chunks):
            return None, "scenario_invalid"
    elif "stall_after_chunk" in body or "stall_timeout_ms" in body:
        return None, "scenario_invalid"
    if kind == "http-error":
        if type(http_status) is not int or not 400 <= http_status <= 599:
            return None, "scenario_invalid"
    elif "http_status" in body:
        return None, "scenario_invalid"
    if request_seq is not None and (type(request_seq) is not int or request_seq < 1):
        return None, "scenario_invalid"
    if (len(chunks) - 1) * delay_ms + (stall_timeout_ms if kind == "stall" else 0) > MAX_STALL_MS:
        return None, "scenario_invalid"
    if _response_size(chunks) > MAX_RESPONSE_BYTES:
        return None, "scenario_invalid"

    return {
        "model": body["model"],
        "kind": kind,
        "chunks": chunks,
        "chunk_delay_ms": delay_ms,
        "stall_after_chunk": stall_after,
        "stall_timeout_ms": stall_timeout_ms,
        "http_status": http_status,
        "request_seq": request_seq,
    }, None


def _stable_embedding(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [digest[index % len(digest)] / 255.0 for index in range(384)]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def _text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return []


def _input_summary(payload: dict[str, Any], is_embedding: bool) -> dict[str, Any]:
    digest = hashlib.sha256()
    sentinels: set[str] = set()
    roles: dict[str, int] = {}
    characters = 0
    text_count = 0
    if is_embedding:
        texts = _text_values(payload.get("input"))
        for text in texts:
            digest.update(text.encode("utf-8"))
            digest.update(b"\x00")
            characters += len(text)
            text_count += 1
            sentinels.update(SENTINEL_PATTERN.findall(text))
        source_count = len(texts)
    else:
        messages = payload.get("messages")
        if not isinstance(messages, list):
            messages = []
        source_count = len(messages)
        for message in messages:
            if not isinstance(message, dict):
                digest.update(b"invalid-message\x00")
                continue
            role = message.get("role")
            role_name = (
                role
                if isinstance(role, str)
                and role in {"system", "user", "assistant", "tool", "developer"}
                else "other"
            )
            roles[role_name] = roles.get(role_name, 0) + 1
            content = message.get("content")
            if isinstance(content, str):
                digest.update(content.encode("utf-8"))
                digest.update(b"\x00")
                characters += len(content)
                text_count += 1
                sentinels.update(SENTINEL_PATTERN.findall(content))
            else:
                digest.update(b"non-text-content\x00")
    return {
        "item_count": source_count,
        "text_count": text_count,
        "characters": characters,
        "role_counts": dict(sorted(roles.items())[:20]),
        "sha256": digest.hexdigest(),
        "sentinel_matches": sorted(sentinels)[:20],
    }


def _message_summaries(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    messages = payload.get("messages", [])
    if not isinstance(messages, list):
        return [], False
    summaries = []
    for message in messages[:MAX_MESSAGE_SUMMARIES]:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        safe_role = (
            role
            if isinstance(role, str)
            and role in {"system", "user", "assistant", "tool", "developer"}
            else "other"
        )
        content = message.get("content")
        text = content if isinstance(content, str) else ""
        summaries.append(
            {
                "role": safe_role,
                "characters": len(text),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return summaries, len(messages) > MAX_MESSAGE_SUMMARIES


def _generation_params(payload: dict[str, Any]) -> dict[str, int | float]:
    safe = {}
    for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty", "seed", "n"):
        value = payload.get(key)
        if type(value) in {int, float} and math.isfinite(value) and abs(value) <= 10**12:
            safe[key] = value
    return safe


class ProviderState:
    """单个Provider实例的场景、屏障和安全观测状态。"""

    def __init__(self, instance_id: str, model_token: str, control_token: str) -> None:
        if not model_token or not control_token or hmac.compare_digest(model_token, control_token):
            raise ValueError("distinct model and control credentials are required")
        self.instance_id = instance_id
        self.model_token = model_token
        self.control_token = control_token
        self.condition = threading.Condition(threading.RLock())
        self.scenarios = self._default_scenarios()
        self.requests: list[dict[str, Any]] = []
        self.records_by_seq: dict[int, dict[str, Any]] = {}
        self.release_events: dict[int, threading.Event] = {}
        self.request_seq = 0
        self.active_requests = 0
        self.dropped_count = 0
        self.retained_bytes = 0
        self.truncated = False

    @staticmethod
    def _default_scenarios() -> dict[str, dict[str, Any]]:
        models = ("ws-http-a", "ws-http-b", "ws-embedding-384")
        return {
            model: {
                "model": model,
                "kind": "normal",
                "chunks": list(DEFAULT_CHUNKS),
                "chunk_delay_ms": 0,
                "stall_after_chunk": None,
                "stall_timeout_ms": MAX_STALL_MS,
                "http_status": 503,
                "request_seq": None,
            }
            for model in models
        }

    def _cost(self, record: dict[str, Any]) -> int:
        # 为阶段字段变化预留最长编码长度，避免推进屏障时突破总字节上限。
        reserved = {**record, "phase": "waiting_release"}
        return len(_json_bytes(reserved))

    def receive(
        self, path: str, model: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        with self.condition:
            sequence = self.request_seq + 1
            configured = self.scenarios.get(model)
            if configured is None:
                return None, None
            scenario = deepcopy(configured)
            if scenario["request_seq"] is not None and scenario["request_seq"] != sequence:
                scenario.update(
                    kind="normal",
                    chunks=list(DEFAULT_CHUNKS),
                    chunk_delay_ms=0,
                    stall_after_chunk=None,
                    request_seq=None,
                )
            self.request_seq = sequence
            summaries, summaries_truncated = _message_summaries(payload)
            record = {
                "request_seq": sequence,
                "path": path,
                "model": model,
                "scenario": scenario["kind"],
                "phase": "received",
                "received": True,
                "first_delta": False,
                "waiting_release": False,
                "finished": False,
                "stall_timed_out": False,
                "stream": payload.get("stream") is True,
                "max_tokens": payload.get("max_tokens")
                if type(payload.get("max_tokens")) is int
                and 0 <= payload["max_tokens"] <= 1_000_000
                else None,
                "input": _input_summary(payload, path.endswith("/embeddings")),
                "message_summaries": summaries,
                "message_summaries_truncated": summaries_truncated,
                "generation_params": _generation_params(payload),
            }
            cost = self._cost(record)
            if (
                len(self.requests) < MAX_OBSERVATIONS
                and self.retained_bytes + cost <= MAX_OBSERVATION_BYTES
            ):
                self.requests.append(record)
                self.records_by_seq[sequence] = record
                self.release_events[sequence] = threading.Event()
                self.retained_bytes += cost
            else:
                self.truncated = True
                self.dropped_count += 1
                record["observation_dropped"] = True
                self.release_events[sequence] = threading.Event()
            self.active_requests += 1
            self.condition.notify_all()
            return record, scenario

    def advance(self, sequence: int, phase: str, *, timed_out: bool = False) -> None:
        with self.condition:
            record = self.records_by_seq.get(sequence)
            if record is not None:
                record[phase] = True
                record["phase"] = phase
                if timed_out:
                    record["stall_timed_out"] = True
            self.condition.notify_all()

    def finish(self, sequence: int) -> None:
        with self.condition:
            record = self.records_by_seq.get(sequence)
            if record is not None:
                record["finished"] = True
                record["phase"] = "finished"
            self.active_requests -= 1
            self.release_events.pop(sequence, None)
            self.condition.notify_all()

    def observe(
        self, request_seq: int | None, wait_for: str | None, timeout_ms: int
    ) -> tuple[int, dict[str, Any]]:
        with self.condition:
            if wait_for is not None and (request_seq is None or wait_for not in ALLOWED_PHASES):
                return 400, _error("observation_query_invalid")
            if request_seq is not None:
                record = self.records_by_seq.get(request_seq)
                deadline = time.monotonic() + timeout_ms / 1000
                if record is None and wait_for is not None and request_seq > self.request_seq:
                    while record is None:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return 200, {
                                "instance_id": self.instance_id,
                                "reached": False,
                                "request": None,
                            }
                        self.condition.wait(remaining)
                        record = self.records_by_seq.get(request_seq)
                if record is None:
                    return 404, _error("observation_not_found")
                if wait_for:
                    while not record[wait_for]:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        self.condition.wait(remaining)
                return 200, {
                    "instance_id": self.instance_id,
                    "reached": record[wait_for] if wait_for else True,
                    "request": deepcopy(record),
                }
            return 200, {
                "instance_id": self.instance_id,
                "count": self.request_seq,
                "requests": deepcopy(self.requests),
                "truncated": self.truncated,
                "dropped_count": self.dropped_count,
                "retained_bytes": self.retained_bytes,
                "max_requests": MAX_OBSERVATIONS,
                "max_bytes": MAX_OBSERVATION_BYTES,
                "active_requests": self.active_requests,
            }

    def configure(self, scenario: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        with self.condition:
            if self.active_requests:
                return 409, _error("requests_in_flight")
            if scenario["model"] not in self.scenarios and len(self.scenarios) >= MAX_SCENARIOS:
                return 400, _error("scenario_capacity_exceeded")
            self.scenarios[scenario["model"]] = scenario
            return 200, {"status": "configured", "scenario": scenario["kind"]}

    def reset(self) -> tuple[int, dict[str, Any]]:
        with self.condition:
            if self.active_requests:
                return 409, _error("requests_in_flight")
            self.scenarios = self._default_scenarios()
            self.requests.clear()
            self.records_by_seq.clear()
            self.release_events.clear()
            self.request_seq = 0
            self.dropped_count = 0
            self.retained_bytes = 0
            self.truncated = False
            self.condition.notify_all()
            return 200, {"status": "reset", "instance_id": self.instance_id}

    def release(self, model: Any, request_seq: Any) -> tuple[int, dict[str, Any]]:
        if not _valid_model(model) or type(request_seq) is not int or request_seq < 1:
            return 400, _error("release_invalid")
        with self.condition:
            record = self.records_by_seq.get(request_seq)
            event = self.release_events.get(request_seq)
            if record is None or event is None or record["model"] != model:
                return 404, _error("release_target_not_found")
            if not record["waiting_release"] or record["finished"]:
                return 409, _error("release_barrier_not_waiting")
            event.set()
            self.condition.notify_all()
            return 200, {"status": "released", "request_seq": request_seq}


class ProviderHandler(BaseHTTPRequestHandler):
    server_version = "SesRAGFixture/1"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)

    @property
    def state(self) -> ProviderState:
        return self.server.provider_state  # type: ignore[attr-defined,no-any-return]

    @property
    def role(self) -> str:
        return self.server.provider_role  # type: ignore[attr-defined,no-any-return]

    def log_message(self, _format: str, *_args: Any) -> None:
        # 默认访问日志可能包含路径或请求头，受控Provider不输出请求相关日志。
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self, maximum: int) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, _error("invalid_length"))
            return None
        if not 0 < length <= maximum:
            self.close_connection = True
            self._send_json(413 if length > maximum else 400, _error("body_limit"))
            return None
        try:
            body = json.loads(self.rfile.read(length))
            # JSON转义可构造无效Unicode代理字符，必须在摘要或回包编码前拒绝。
            _json_bytes(body)
        except (UnicodeError, ValueError):
            self._send_json(400, _error("invalid_json"))
            return None
        if not isinstance(body, dict):
            self._send_json(400, _error("object_required"))
            return None
        return body

    def _authorized(self, credential: str) -> bool:
        actual = self.headers.get("Authorization", "")
        expected = f"Bearer {credential}"
        if credential and hmac.compare_digest(actual.encode("utf-8"), expected.encode("utf-8")):
            return True
        self._send_json(401, _error("unauthorized"))
        return False

    def _health(self) -> None:
        self._send_json(200, {"status": "ok", "instance_id": self.state.instance_id})

    def _not_found(self) -> None:
        self._send_json(404, _error("not_found"))

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self._health()
            return
        if self.role != "control":
            self._not_found()
            return
        if path == "/control/health":
            if self._authorized(self.state.control_token):
                self._health()
            return
        if path == "/control/observations":
            if not self._authorized(self.state.control_token):
                return
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            if set(query) - {"request_seq", "wait_for", "timeout_ms"}:
                self._send_json(400, _error("observation_query_invalid"))
                return
            try:
                request_seq = int(query["request_seq"][0]) if "request_seq" in query else None
                timeout_ms = int(query.get("timeout_ms", ["0"])[0])
            except (ValueError, IndexError):
                self._send_json(400, _error("observation_query_invalid"))
                return
            wait_for = query.get("wait_for", [None])[0]
            if (
                timeout_ms < 0
                or timeout_ms > MAX_STALL_MS
                or request_seq is not None
                and request_seq < 1
            ):
                self._send_json(400, _error("observation_query_invalid"))
                return
            status, response = self.state.observe(request_seq, wait_for, timeout_ms)
            self._send_json(status, response)
            return
        self._not_found()

    def do_PUT(self) -> None:
        path = urlsplit(self.path).path
        if self.role != "control" or path != "/control/scenario":
            self._not_found()
            return
        if not self._authorized(self.state.control_token):
            return
        body = self._read_json(MAX_CONTROL_BODY_BYTES)
        if body is None:
            return
        scenario, error = _validated_scenario(body)
        if error:
            self._send_json(400, _error(error))
            return
        status, response = self.state.configure(scenario)
        self._send_json(status, response)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if self.role == "control":
            if path not in {"/control/reset", "/control/release"}:
                self._not_found()
                return
            if not self._authorized(self.state.control_token):
                return
            body = self._read_json(16 * 1024)
            if body is None:
                return
            if body.get("schema_version") != 1 or type(body.get("schema_version")) is not int:
                self._send_json(400, _error("control_version_unsupported"))
                return
            if path == "/control/reset":
                if set(body) != {"schema_version"}:
                    self._send_json(400, _error("control_request_invalid"))
                    return
                status, response = self.state.reset()
                self._send_json(status, response)
                return
            if set(body) != {"schema_version", "model", "request_seq"}:
                self._send_json(400, _error("release_invalid"))
                return
            status, response = self.state.release(body.get("model"), body.get("request_seq"))
            self._send_json(status, response)
            return

        if path not in {"/v1/chat/completions", "/v1/embeddings"}:
            self._not_found()
            return
        if not self._authorized(self.state.model_token):
            return
        payload = self._read_json(MAX_INFERENCE_BODY_BYTES)
        if payload is None:
            return
        model = payload.get("model")
        if not _valid_model(model):
            self._send_json(400, _error("model_invalid"))
            return
        if path.endswith("/chat/completions") and not isinstance(payload.get("messages"), list):
            self._send_json(400, _error("messages_invalid"))
            return
        if path.endswith("/embeddings"):
            texts = _text_values(payload.get("input"))
            if not texts:
                self._send_json(400, _error("embedding_input_invalid"))
                return
            if len(texts) > MAX_EMBEDDING_BATCH:
                self._send_json(400, _error("embedding_batch_limit"))
                return

        with self.state.condition:
            if self.state.active_requests >= MAX_ACTIVE_REQUESTS:
                self._send_json(429, _error("provider_busy"))
                return
            record, scenario = self.state.receive(path, model, payload)
        if record is None or scenario is None:
            self._send_json(400, _error("scenario_not_configured"))
            return
        sequence = record["request_seq"]
        try:
            if path.endswith("/embeddings"):
                self._serve_embeddings(payload, scenario)
            else:
                self._serve_completion(scenario, sequence)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True
        finally:
            self.state.finish(sequence)

    def _serve_embeddings(self, payload: dict[str, Any], scenario: dict[str, Any]) -> None:
        kind = scenario["kind"]
        if kind == "http-error":
            self._send_json(scenario["http_status"], _error("fixture_http_error"))
            return
        if kind == "context-limit":
            self._send_json(400, _error("context_length_exceeded"))
            return
        texts = _text_values(payload["input"])
        if len(texts) > MAX_EMBEDDING_BATCH:
            self._send_json(400, _error("embedding_batch_limit"))
            return
        vectors = [
            {"object": "embedding", "index": index, "embedding": _stable_embedding(text)}
            for index, text in enumerate(texts)
        ]
        self._send_json(200, {"object": "list", "data": vectors, "model": payload["model"]})

    def _serve_completion(self, scenario: dict[str, Any], sequence: int) -> None:
        kind = scenario["kind"]
        if kind == "http-error":
            self._send_json(scenario["http_status"], _error("fixture_http_error"))
            return
        if kind == "context-limit":
            self._send_json(400, _error("context_length_exceeded"))
            return
        if kind == "disconnect":
            self.close_connection = True
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        if kind == "partial-disconnect":
            self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        if kind == "partial-disconnect":
            # UI_003：先让真实首delta有机会提交，再制造缺HTTP终结chunk的传输故障。
            packet = _encoded_frame(_json_bytes(_chunk_packet(scenario["chunks"][0])))
            self.wfile.write(f"{len(packet):X}\r\n".encode() + packet + b"\r\n")
            self.wfile.flush()
            self.state.advance(sequence, "first_delta")
            time.sleep(0.3)
            self.close_connection = True
            return
        if kind == "malformed":
            self.wfile.write(b"data: {not-json}\n\n")
            self.wfile.flush()
            return
        if kind == "empty":
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return

        chunks = scenario["chunks"]
        release_event = self.state.release_events.get(sequence, threading.Event())
        for index, content in enumerate(chunks, start=1):
            self.wfile.write(_encoded_frame(_json_bytes(_chunk_packet(content))))
            self.wfile.flush()
            if index == 1:
                self.state.advance(sequence, "first_delta")
            if kind == "stall" and index == scenario["stall_after_chunk"]:
                self.state.advance(sequence, "waiting_release")
                released = release_event.wait(scenario["stall_timeout_ms"] / 1000)
                if not released:
                    self.state.advance(sequence, "waiting_release", timed_out=True)
            if scenario["chunk_delay_ms"] and index < len(chunks):
                time.sleep(scenario["chunk_delay_ms"] / 1000)

        finish = {
            "id": "fixture-completion",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        self.wfile.write(_encoded_frame(_json_bytes(finish)))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, _request: Any, _client_address: Any) -> None:
        # 标准库默认异常日志含宿主路径；这里只保留稳定、无输入的诊断码。
        print('{"event":"provider_handler_error","code":"harness_error"}', file=sys.stderr)


def start_servers(
    host: str,
    inference_port: int,
    control_port: int,
    *,
    state: ProviderState | None = None,
) -> tuple[QuietServer, QuietServer]:
    """为运行服务或仅本机自测创建推理和控制两个独立监听端口。"""
    if inference_port == control_port and inference_port != 0:
        raise ValueError("inference and control ports must differ")
    provider_state = state or ProviderState(
        f"{os.getenv('PROVIDER_INSTANCE_ID', 'fixture')[:96]}-{uuid.uuid4().hex}",
        os.getenv("MODEL_API_KEY", ""),
        os.getenv("PROVIDER_CONTROL_TOKEN", ""),
    )
    inference = QuietServer((host, inference_port), ProviderHandler)
    inference.provider_state = provider_state  # type: ignore[attr-defined]
    inference.provider_role = "inference"  # type: ignore[attr-defined]
    try:
        control = QuietServer((host, control_port), ProviderHandler)
    except OSError:
        inference.server_close()
        raise
    control.provider_state = provider_state  # type: ignore[attr-defined]
    control.provider_role = "control"  # type: ignore[attr-defined]
    return inference, control


def main() -> None:
    model_token = os.getenv("MODEL_API_KEY", "")
    control_token = os.getenv("PROVIDER_CONTROL_TOKEN", "")
    if not model_token or not control_token or hmac.compare_digest(model_token, control_token):
        raise SystemExit("测试 Provider 必须注入互不相同的模型与控制凭据")
    try:
        inference, control = start_servers("0.0.0.0", 8080, 8081)
    except (ValueError, OSError):
        raise SystemExit("测试 Provider 端口配置无效或端口不可用") from None
    threading.Thread(
        target=inference.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True
    ).start()
    try:
        control.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        inference.shutdown()
        control.server_close()
        inference.server_close()


if __name__ == "__main__":
    main()
