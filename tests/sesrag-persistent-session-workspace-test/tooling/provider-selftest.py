"""对运行中的受控 Provider 执行协议自测；不属于产品验收用例。"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_DIR = ROOT / "fixtures" / "provider"
sys.path.insert(0, str(PROVIDER_DIR))

INFERENCE_URL = os.getenv("PROVIDER_INFERENCE_URL", "http://provider:8080")
CONTROL_URL = os.getenv("PROVIDER_CONTROL_URL", "http://provider:8081")
MODEL_TOKEN = os.getenv("MODEL_API_KEY", "")
CONTROL_TOKEN = os.getenv("PROVIDER_CONTROL_TOKEN", "")
MODEL = "provider-selftest-model"
MAX_CHUNK_BYTES = 65_536
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class SelfTestFailure(RuntimeError):
    """以不含请求正文或凭据的消息中止自测。"""


def request_json(
    base: str,
    method: str,
    path: str,
    payload: Any = None,
    token: str | None = None,
    *,
    timeout: float = 5,
) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(base.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed
    except (URLError, TimeoutError, OSError) as exc:
        raise SelfTestFailure(f"{method} {path} transport failed ({type(exc).__name__})") from None


def request_sse(payload: dict[str, Any], token: str | None = None) -> tuple[int, bytes, str]:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(
        INFERENCE_URL.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(req, timeout=10) as response:
            return response.status, response.read(), response.headers.get("Content-Type", "")
    except HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Content-Type", "")
    except (URLError, TimeoutError, OSError) as exc:
        raise SelfTestFailure(f"chat completion transport failed ({type(exc).__name__})") from None


def request_slow_sse(payload: dict[str, Any]) -> tuple[int, bytes, str]:
    """逐帧观察慢流，不能仅以最终正文中有多个片段代替等待行为。"""
    req = Request(
        INFERENCE_URL.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {MODEL_TOKEN}"},
        method="POST",
    )
    with urlopen(req, timeout=10) as response:
        lines = []
        arrivals = []
        while line := response.readline():
            lines.append(line)
            if line.startswith(b"data: ") and b"[DONE]" not in line:
                arrivals.append(time.monotonic())
        check(len(arrivals) >= 3, "slow scenario did not expose individual streamed frames")
        check(
            arrivals[1] - arrivals[0] >= 0.12 and arrivals[2] - arrivals[1] >= 0.12,
            "slow scenario did not preserve configured inter-frame waits",
        )
        return response.status, b"".join(lines), response.headers.get("Content-Type", "")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SelfTestFailure(message)


def decode_sse(body: bytes) -> list[dict[str, Any]]:
    check(body.endswith(b"\n\n"), "SSE stream ended inside a frame")
    frames = body.split(b"\n\n")[:-1]
    check(frames and frames[-1] == b"data: [DONE]", "SSE terminal marker was not last")
    packets = []
    for frame in frames[:-1]:
        check(frame.startswith(b"data: "), "SSE data prefix was invalid")
        try:
            packet = json.loads(frame[6:])
        except (UnicodeError, ValueError):
            raise SelfTestFailure("normal SSE contained invalid JSON") from None
        check(isinstance(packet, dict), "normal SSE packet was not an object")
        check(packet.get("object") == "chat.completion.chunk", "SSE chunk object type was invalid")
        choices = packet.get("choices")
        check(isinstance(choices, list) and len(choices) == 1, "SSE choices were invalid")
        check(choices[0].get("index") == 0, "SSE choice index was invalid")
        packets.append(packet)
    return packets


def control_scenario(kind: str, *, timeout: float = 5, **options: Any) -> tuple[int, Any]:
    return request_json(
        CONTROL_URL,
        "PUT",
        "/control/scenario",
        {"schema_version": 1, "kind": kind, "model": MODEL, **options},
        CONTROL_TOKEN,
        timeout=timeout,
    )


def reset_provider() -> None:
    status, _ = request_json(
        CONTROL_URL, "POST", "/control/reset", {"schema_version": 1}, CONTROL_TOKEN
    )
    check(status == 200, "control reset failed")


def observations(**query: Any) -> tuple[int, Any]:
    suffix = "?" + urlencode(query) if query else ""
    return request_json(CONTROL_URL, "GET", "/control/observations" + suffix, token=CONTROL_TOKEN)


def wait_barrier(request_seq: int, phase: str, timeout_ms: int = 2_000) -> dict[str, Any]:
    status, body = observations(
        request_seq=request_seq,
        wait_for=phase,
        timeout_ms=timeout_ms,
    )
    check(status == 200 and isinstance(body, dict), f"{phase} barrier response invalid")
    check(body.get("reached") is True, f"{phase} barrier was not reached")
    record = body.get("request")
    check(isinstance(record, dict), f"{phase} barrier has no request summary")
    return record


def completion_payload() -> dict[str, Any]:
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": "selftest synthetic prompt"}],
        "stream": True,
    }


def test_health_and_port_credential_isolation() -> None:
    status, health = request_json(INFERENCE_URL, "GET", "/health")
    check(status == 200 and health.get("status") == "ok", "inference health failed")
    status, health = request_json(CONTROL_URL, "GET", "/health")
    check(status == 200 and health.get("status") == "ok", "control health failed")

    status, _ = request_json(INFERENCE_URL, "POST", "/v1/chat/completions", completion_payload())
    check(status == 401, "inference accepted a request without its credential")
    status, _ = request_json(CONTROL_URL, "GET", "/control/observations")
    check(status == 401, "control port accepted a request without its credential")
    status, _ = request_json(INFERENCE_URL, "PUT", "/control/scenario", {}, MODEL_TOKEN)
    check(status == 404, "inference port exposed control endpoints")
    status, _ = request_json(CONTROL_URL, "POST", "/v1/chat/completions", {}, CONTROL_TOKEN)
    check(status == 404, "control port exposed inference endpoints")
    status, _ = request_json(CONTROL_URL, "GET", "/control/observations", token=MODEL_TOKEN)
    check(status == 401, "model credential authorized control access")
    status, _ = request_json(
        INFERENCE_URL, "POST", "/v1/chat/completions", completion_payload(), CONTROL_TOKEN
    )
    check(status == 401, "control credential authorized inference access")


def test_scenario_schema_and_bounded_limits() -> None:
    reset_provider()
    status, body = request_json(
        CONTROL_URL,
        "PUT",
        "/control/scenario",
        {"kind": "normal", "model": MODEL},
        CONTROL_TOKEN,
    )
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_version_unsupported",
        "missing schema version was accepted",
    )
    status, body = control_scenario("not-a-scenario")
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_invalid",
        "invalid scenario was accepted",
    )
    status, body = control_scenario(["normal"])
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_invalid",
        "non-string scenario kind was not rejected safely",
    )

    status, body = control_scenario("normal", chunk_delay_ms=2_001)
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_invalid",
        "unbounded delay was accepted",
    )
    status, body = control_scenario("normal", chunks=["x" * (MAX_CHUNK_BYTES + 1)])
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_invalid",
        "oversized chunk was accepted",
    )
    status, body = control_scenario("normal", chunks=["x"] * 8_193)
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_invalid",
        "too many chunks were accepted",
    )
    status, body = control_scenario("stall", stall_timeout_ms=180_001)
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_invalid",
        "unbounded stall was accepted",
    )
    status, _ = control_scenario("stall", stall_timeout_ms=180_000)
    check(status == 200, "maximum legal stall timeout was rejected")
    status, body = control_scenario("http-error", http_status=200)
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_invalid",
        "invalid HTTP error status was accepted",
    )
    status, body = control_scenario("normal", schema_version=2)
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_version_unsupported",
        "unsupported schema version was accepted",
    )

    # 正文仍低于控制请求体上限，专门核验整段响应超限会被拒绝。
    large_chunks = ["x" * MAX_CHUNK_BYTES for _ in range(129)]
    status, body = control_scenario("normal", timeout=20, chunks=large_chunks)
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_invalid",
        "oversized aggregate response was accepted",
    )

    status, body = control_scenario("normal")
    check(status == 200, "model-scoped valid scenario was rejected")
    status, body = request_json(
        INFERENCE_URL,
        "POST",
        "/v1/chat/completions",
        {**completion_payload(), "model": "unconfigured-selftest-model"},
        MODEL_TOKEN,
    )
    check(
        status == 400 and body.get("error", {}).get("code") == "scenario_not_configured",
        "unconfigured model silently selected a scenario",
    )

    parsed = urlsplit(INFERENCE_URL)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
    try:
        # 只发送短正文并声明超限长度，确认服务器在读取完整请求前立即拒绝。
        connection.request(
            "POST",
            "/v1/embeddings",
            body=b"{}",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(2 * 1024 * 1024 + 1),
                "Authorization": f"Bearer {MODEL_TOKEN}",
            },
        )
        response = connection.getresponse()
        check(response.status == 413, "oversized inference request was not rejected")
        response.read()
    finally:
        connection.close()


def test_normal_slow_and_failure_scenarios() -> None:
    cases = [
        ("normal", 200, True, b"[DONE]"),
        ("slow", 200, True, b"[DONE]"),
        ("empty", 200, True, b"[DONE]"),
        ("malformed", 200, True, b"{not-json}"),
        ("context-limit", 400, False, b"context_length_exceeded"),
        ("http-error", 503, False, b"fixture_http_error"),
    ]
    for kind, expected_status, is_sse, expected_marker in cases:
        reset_provider()
        options = {"chunk_delay_ms": 5}
        if kind == "slow":
            options = {"chunk_delay_ms": 180, "chunks": ["first", "second", "third"]}
        if kind == "http-error":
            options["http_status"] = 503
        status, _ = control_scenario(kind, **options)
        check(status == 200, f"{kind} scenario could not be configured")
        status, body, content_type = (
            request_slow_sse(completion_payload())
            if kind == "slow"
            else request_sse(completion_payload(), MODEL_TOKEN)
        )
        check(status == expected_status, f"{kind} scenario returned an unexpected status")
        check(
            content_type.startswith("text/event-stream") == is_sse,
            f"{kind} scenario returned an unexpected stream",
        )
        check(expected_marker in body, f"{kind} scenario marker was missing")
        if kind in {"normal", "slow"}:
            packets = decode_sse(body)
            check(len(packets) >= 3, "normal stream did not contain content and finish packets")
            check(
                packets[-1]["choices"][0].get("finish_reason") == "stop",
                "normal stream finish reason was invalid",
            )
            check(
                all(isinstance(packet["choices"][0].get("delta"), dict) for packet in packets),
                "normal stream delta was invalid",
            )
        elif kind == "empty":
            check(
                decode_sse(body) == [], "empty scenario unexpectedly contained completion packets"
            )
        if kind == "normal":
            check(
                body.count(b"chat.completion.chunk") >= 2,
                "normal scenario did not stream multiple chunks",
            )
        if kind == "slow":
            check(
                body.count(b"chat.completion.chunk") >= 2,
                "slow scenario did not stream multiple chunks",
            )

    reset_provider()
    status, _ = control_scenario("disconnect")
    check(status == 200, "disconnect scenario could not be configured")
    try:
        request_sse(completion_payload(), MODEL_TOKEN)
    except SelfTestFailure as exc:
        check("transport failed" in str(exc), "disconnect failed for an unexpected reason")
    else:
        raise SelfTestFailure("disconnect scenario returned a normal response")


def test_embedding_batch_is_stable_and_ordered() -> None:
    reset_provider()
    status, _ = control_scenario("normal")
    check(status == 200, "embedding scenario could not be configured")
    inputs = ["same input", "different input", "same input"]
    payload = {"model": MODEL, "input": inputs}
    first_status, first = request_json(
        INFERENCE_URL, "POST", "/v1/embeddings", payload, MODEL_TOKEN
    )
    second_status, second = request_json(
        INFERENCE_URL, "POST", "/v1/embeddings", payload, MODEL_TOKEN
    )
    check(first_status == second_status == 200, "embedding request failed")
    rows = first.get("data", [])
    check(
        [row.get("index") for row in rows] == [0, 1, 2],
        "embedding batch indices are not in input order",
    )
    check(len(rows) == len(inputs), "embedding batch size did not match the input")
    vectors = [row.get("embedding") for row in rows]
    check(
        all(isinstance(vector, list) and len(vector) == 384 for vector in vectors),
        "embedding dimension is not 384",
    )
    check(
        vectors[0] == vectors[2]
        and vectors == [row["embedding"] for row in second.get("data", [])],
        "embedding output is not stable by input",
    )
    check(
        all(math.isfinite(value) for vector in vectors for value in vector),
        "embedding contains a non-finite value",
    )
    norm = math.sqrt(sum(value * value for value in vectors[0]))
    check(abs(norm - 1.0) < 1e-6, "embedding vector is not normalized")
    status, body = request_json(
        INFERENCE_URL,
        "POST",
        "/v1/embeddings",
        {"model": "ws-embedding-384", "input": "baseline embedding input"},
        MODEL_TOKEN,
    )
    check(status == 200 and len(body["data"]) == 1, "baseline embedding model was unavailable")
    status, body = request_json(
        INFERENCE_URL,
        "POST",
        "/v1/embeddings",
        {"model": MODEL, "input": ["x"] * 257},
        MODEL_TOKEN,
    )
    check(
        status == 400 and body.get("error", {}).get("code") == "embedding_batch_limit",
        "oversized embedding batch was accepted",
    )


def test_observations_only_expose_safe_summaries() -> None:
    reset_provider()
    status, _ = control_scenario("normal")
    check(status == 200, "summary scenario could not be configured")
    synthetic_secret = "private-selftest-not-for-observations"
    synthetic_prompt = "selftest-sensitive-prompt HISTORY-ABCD-1234"
    payload = {
        **completion_payload(),
        "messages": [
            {"role": "system", "content": synthetic_secret},
            {"role": "user", "content": synthetic_prompt},
        ],
        "max_tokens": 123,
        "temperature": 0.2,
        "top_p": 0.7,
        "metadata": {"secret": synthetic_secret},
    }
    status, _, _ = request_sse(payload, MODEL_TOKEN)
    check(status == 200, "summary source request failed")
    status, body = observations()
    check(status == 200, "summary observations were unavailable")
    serialized = json.dumps(body)
    check(
        all(
            value not in serialized
            for value in (synthetic_secret, synthetic_prompt, MODEL_TOKEN, CONTROL_TOKEN)
        ),
        "observation response exposed request content or credentials",
    )
    row = body["requests"][0]
    check(row.get("max_tokens") == 123, "safe max_tokens summary was missing")
    check(
        row.get("generation_params") == {"temperature": 0.2, "top_p": 0.7},
        "safe generation parameters were missing",
    )
    message_summaries = row.get("message_summaries", [])
    check(
        [item.get("role") for item in message_summaries] == ["system", "user"],
        "message role summaries were missing",
    )
    check(
        [item.get("characters") for item in message_summaries] == [37, 43],
        "message length summaries were incorrect",
    )
    check(
        all(len(item.get("sha256", "")) == 64 for item in message_summaries),
        "message digest summaries were missing",
    )
    check(
        "HISTORY-ABCD-1234" in row.get("input", {}).get("sentinel_matches", []),
        "allowlisted synthetic sentinel match was missing",
    )


def test_scenario_matches_the_configured_request_sequence() -> None:
    reset_provider()
    status, _ = control_scenario("context-limit", request_seq=2)
    check(status == 200, "sequence-scoped scenario could not be configured")
    status, body, _ = request_sse(completion_payload(), MODEL_TOKEN)
    check(
        status == 200 and b"[DONE]" in body,
        "request before target sequence did not use normal behavior",
    )
    status, body, _ = request_sse(completion_payload(), MODEL_TOKEN)
    check(
        status == 400 and b"context_length_exceeded" in body,
        "target sequence did not use its configured scenario",
    )
    status, body, _ = request_sse(completion_payload(), MODEL_TOKEN)
    check(
        status == 200 and b"[DONE]" in body,
        "request after target sequence did not return to normal behavior",
    )
    status, body = observations()
    check(status == 200, "sequence-scoped observations could not be read")
    check(
        [item["scenario"] for item in body["requests"]] == ["normal", "context-limit", "normal"],
        "scenario was not matched to the request sequence",
    )


def test_observation_barriers_and_release() -> None:
    reset_provider()
    status, _ = control_scenario(
        "stall",
        chunks=["first synthetic delta", "second synthetic delta"],
        stall_after_chunk=1,
        stall_timeout_ms=5_000,
    )
    check(status == 200, "stall scenario could not be configured")

    result: dict[str, Any] = {}

    def send_request() -> None:
        try:
            result["response"] = request_sse(completion_payload(), MODEL_TOKEN)
        except SelfTestFailure as exc:
            result["failure"] = str(exc)

    worker = threading.Thread(target=send_request, daemon=True)
    worker.start()
    request_seq = 1
    received = wait_barrier(request_seq, "received")
    first_delta = wait_barrier(request_seq, "first_delta")
    waiting = wait_barrier(request_seq, "waiting_release")
    check(received.get("received") is True, "request receipt barrier was not recorded")
    check(
        first_delta.get("first_delta") is True and waiting.get("waiting_release") is True,
        "barrier phase flags were not recorded",
    )

    status, body = control_scenario("normal")
    check(
        status == 409 and body.get("error", {}).get("code") == "requests_in_flight",
        "in-flight scenario change was accepted",
    )
    status, body = request_json(
        CONTROL_URL, "POST", "/control/reset", {"schema_version": 1}, CONTROL_TOKEN
    )
    check(
        status == 409 and body.get("error", {}).get("code") == "requests_in_flight",
        "in-flight reset was accepted",
    )
    status, _ = request_json(
        CONTROL_URL,
        "POST",
        "/control/release",
        {"schema_version": 1, "model": "wrong-model", "request_seq": request_seq},
        CONTROL_TOKEN,
    )
    check(status == 404, "release accepted a different model")

    status, _ = request_json(
        CONTROL_URL,
        "POST",
        "/control/release",
        {"schema_version": 1, "model": MODEL, "request_seq": request_seq},
        CONTROL_TOKEN,
    )
    check(status == 200, "release did not unblock the request")
    finished = wait_barrier(request_seq, "finished")
    worker.join(timeout=3)
    check(not worker.is_alive() and "response" in result, "released request did not finish")
    check(finished.get("finished") is True, "finished barrier was not recorded")
    check(
        result["response"][0] == 200 and b"[DONE]" in result["response"][1],
        "released stream did not complete",
    )


def test_future_receipt_barrier_has_a_bounded_timeout() -> None:
    reset_provider()
    status, body = observations(request_seq=1, wait_for="received", timeout_ms=50)
    check(status == 200 and body.get("reached") is False, "future receipt did not time out safely")
    check(body.get("request") is None, "future receipt invented an observation")


def test_stall_expires_without_release() -> None:
    reset_provider()
    status, _ = control_scenario("stall", stall_timeout_ms=50)
    check(status == 200, "bounded stall could not be configured")
    status, body, _ = request_sse(completion_payload(), MODEL_TOKEN)
    check(status == 200 and b"[DONE]" in body, "bounded stall did not finish after timeout")
    record = wait_barrier(1, "finished")
    check(record.get("stall_timed_out") is True, "bounded stall timeout was not recorded")


def test_observation_capacity_is_explicitly_truncated() -> None:
    reset_provider()
    status, initial = observations()
    check(status == 200, "observation capacity discovery failed")
    capacity = initial.get("max_requests")
    check(type(capacity) is int and 1 <= capacity <= 2000, "observation capacity outside bound")
    status, _ = control_scenario("normal", chunks=["ok"])
    check(status == 200, "normal scenario could not be configured")
    for _ in range(capacity + 5):
        status, _ = request_json(
            INFERENCE_URL,
            "POST",
            "/v1/embeddings",
            {"model": MODEL, "input": "bounded synthetic input"},
            MODEL_TOKEN,
        )
        check(status == 200, "bounded observation request failed")
    status, body = observations()
    check(status == 200, "observation retrieval failed")
    rows = body.get("requests", [])
    check(len(rows) <= capacity, "observation count exceeded configured capacity")
    check(
        body.get("truncated") is True and body.get("dropped_count", 0) >= 5,
        "observation overflow was not marked",
    )
    check(
        body.get("retained_bytes", MAX_RESPONSE_BYTES + 1) <= MAX_RESPONSE_BYTES,
        "observation bytes exceeded 8 MiB",
    )


def run_tests() -> list[str]:
    check(bool(MODEL_TOKEN), "MODEL_API_KEY is required for a running Provider")
    check(bool(CONTROL_TOKEN), "PROVIDER_CONTROL_TOKEN is required for a running Provider")
    health = request_json(INFERENCE_URL, "GET", "/health")[1]
    control_health = request_json(CONTROL_URL, "GET", "/health")[1]
    check(
        isinstance(health, dict) and health.get("instance_id"),
        "Provider instance identity is missing",
    )
    check(
        isinstance(control_health, dict)
        and control_health.get("instance_id") == health["instance_id"],
        "Provider instance identity differs by port",
    )

    tests = [
        test_health_and_port_credential_isolation,
        test_scenario_schema_and_bounded_limits,
        test_normal_slow_and_failure_scenarios,
        test_embedding_batch_is_stable_and_ordered,
        test_observations_only_expose_safe_summaries,
        test_scenario_matches_the_configured_request_sequence,
        test_observation_barriers_and_release,
        test_future_receipt_barrier_has_a_bounded_timeout,
        test_stall_expires_without_release,
        test_observation_capacity_is_explicitly_truncated,
    ]
    completed = []
    for test in tests:
        test()
        completed.append(test.__name__)
    reset_provider()
    return completed


def run_standalone() -> list[str]:
    try:
        import server
    except ImportError as exc:
        raise SelfTestFailure(
            f"standalone provider module unavailable ({type(exc).__name__})"
        ) from None

    start = getattr(server, "start_servers", None)
    if start is None:
        raise SelfTestFailure("standalone provider server does not expose the local test factory")

    os.environ["MODEL_API_KEY"] = secrets.token_urlsafe(32)
    os.environ["PROVIDER_CONTROL_TOKEN"] = secrets.token_urlsafe(32)
    try:
        inference, control = start("127.0.0.1", 0, 0)
    except (ValueError, OSError):
        raise SelfTestFailure("standalone provider could not bind local test ports") from None
    threads = [
        threading.Thread(target=inference.serve_forever, daemon=True),
        threading.Thread(target=control.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()
    global INFERENCE_URL, CONTROL_URL, MODEL_TOKEN, CONTROL_TOKEN
    INFERENCE_URL = f"http://127.0.0.1:{inference.server_address[1]}"
    CONTROL_URL = f"http://127.0.0.1:{control.server_address[1]}"
    MODEL_TOKEN = os.environ["MODEL_API_KEY"]
    CONTROL_TOKEN = os.environ["PROVIDER_CONTROL_TOKEN"]
    try:
        return run_tests()
    finally:
        inference.shutdown()
        control.shutdown()
        inference.server_close()
        control.server_close()
        for thread in threads:
            thread.join(timeout=2)


def main() -> int:
    global INFERENCE_URL, CONTROL_URL
    parser = argparse.ArgumentParser(description="受控 Provider 协议自测，不执行产品用例")
    parser.add_argument(
        "--standalone", action="store_true", help="仅在本机启动短生命周期 Provider 实例"
    )
    parser.add_argument("--base-url", default=INFERENCE_URL, help="运行中的推理端口地址")
    parser.add_argument("--control-url", default=CONTROL_URL, help="运行中的控制端口地址")
    args = parser.parse_args()
    INFERENCE_URL = args.base_url
    CONTROL_URL = args.control_url
    try:
        if args.standalone:
            checks = run_standalone()
        else:
            checks = run_tests()
    except SelfTestFailure as exc:
        print(json.dumps({"schema_version": 1, "status": "failed", "error": str(exc)}))
        return 1
    except Exception as exc:
        # 未预期异常仅输出类型，避免标准库异常意外回显完整正文或地址。
        print(json.dumps({"schema_version": 1, "status": "failed", "error": type(exc).__name__}))
        return 1
    print(
        json.dumps(
            {
                "schema_version": 1,
                "status": "passed",
                "product_acceptance": "not_run",
                "checks": checks,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
