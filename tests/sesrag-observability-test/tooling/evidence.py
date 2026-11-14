"""本轮结果协议；不持久化原异常、请求正文或凭据。"""

import hashlib
import json
import time
import traceback
from pathlib import Path

import httpx

API = "http://api:8000"
COLLECTOR = "http://collector:4318"


def client():
    return httpx.Client(base_url=API, timeout=10, trust_env=False)


def request(c, method, path, **kwargs):
    response = c.request(method, path, **kwargs)
    if response.status_code >= 400:
        code = response.json().get("code", "HTTP_ERROR")
        raise AssertionError(f"请求失败 status={response.status_code} code={code}")
    return response.json()


def wait(c, path, field="status", timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = request(c, "GET", path)
        state = data["latest_build"]["state"] if "/api/v3/documents/" in path else data[field]
        if state in {"succeeded", "failed", "cancelled"}:
            if state != "succeeded":
                code = (
                    data.get("latest_build", {}).get("error_code")
                    if "/api/v3/documents/" in path
                    else data.get("error_code")
                )
                # B镜像无观测模块，直接读取同一静态错误字典。
                allowed = json.loads(
                    Path("/app/contracts/observability/error_codes_v1.json").read_text()
                )
                safe = code if code in allowed else "UNKNOWN_ERROR"
                raise AssertionError("业务终态不是成功：" + str(safe))
            return data
        time.sleep(0.1)
    raise AssertionError("业务超过独立验证等待预算")


def spans():
    with httpx.Client(trust_env=False) as c:
        return c.get(COLLECTOR + "/evidence").json()


def metrics(role):
    with httpx.Client(trust_env=False, timeout=3) as c:
        response = c.get(f"http://{role}:{9101 if role == 'api' else 9102}/metrics")
        assert response.status_code == 200
        return response.text


def outcome(case, function):
    try:
        evidence = function() or {}
        record = dict(case=case, status="passed", message="验证目标通过", evidence=evidence)
    except Exception as exc:
        # AssertionError仅允许固定中文检查语句；第三方异常不序列化。
        message = (
            str(exc)[:500]
            if type(exc) is AssertionError
            else "执行失败，异常类型：" + type(exc).__name__
        )
        frames = [
            {"file": Path(f.filename).name, "line": f.lineno}
            for f in traceback.extract_tb(exc.__traceback__)
        ]
        record = dict(case=case, status="failed", message=message, evidence={"frames": frames})
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
