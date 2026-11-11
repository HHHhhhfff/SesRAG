"""生产协议保留，只有local入口替换传输；不会放宽SafeHTTP的域/IP守卫。"""

import contextvars
import hashlib
import io
import json
import os
import zipfile

import httpx

SCOPE = contextvars.ContextVar("test_scope", default="unscoped")


async def control(kind, payload=None, scope=None):
    async with httpx.AsyncClient(trust_env=False, timeout=125) as client:
        response = await client.post(
            f"http://scenario-control:8081/step/{scope or SCOPE.get()}/{kind}",
            headers={"Authorization": f"Bearer {os.environ['TEST_CONTROL_TOKEN']}"},
            json=payload or {},
        )
        response.raise_for_status()
        return response.json()


def package(kind="safe"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        text = (
            "# Synthetic office input\n\n合成事实：ALPHA代码对应数值37。\n\n"
            "|项目|值|\n|---|---|\n|ALPHA|37|"
        )
        if kind == "empty":
            text = "  \n"
        if kind == "html":
            text += "\n<script>never_execute()</script>\n![asset](https://invalid.example/a.png)"
        archive.writestr("full.md", text)
        if kind == "escape":
            archive.writestr("../escape.txt", b"synthetic")
        if kind == "nested":
            archive.writestr("other.zip", b"synthetic")
    return stream.getvalue()


async def mineru_transport(request):
    path = request.url.path
    if path.endswith("file-urls/batch"):
        file = json.loads(request.content)["files"][0]
        scope = file["data_id"]
        kind = "mineru_submit"
        payload = {"filename": file["name"], "data_id": scope}
    elif request.method == "PUT":
        scope, kind = path.strip("/").split("/")[-1], "mineru_put"
        if request.headers.get("authorization"):
            raise ValueError("STORAGE_BEARER_LEAK")
        payload = {
            "bytes": len(request.content),
            "sha256": hashlib.sha256(request.content).hexdigest(),
        }
    elif "/extract-results/batch/" in path:
        scope, kind, payload = path.rsplit("/", 1)[-1], "mineru_poll", {}
    elif path.startswith("/download/"):
        scope, kind, payload = path.rsplit("/", 1)[-1], "mineru_download", {}
    else:
        raise ValueError("UNKNOWN_SYNTHETIC_ROUTE")
    result = await control(kind, payload, scope)
    action, remote = result["action"], result["remote"]
    if action.get("fault") == "connection":
        raise httpx.ConnectError("synthetic connection loss", request=request)
    status = action.get("status", 200)
    if "response_json" in action:
        return httpx.Response(status, json=action["response_json"])
    if kind == "mineru_submit":
        data = {"batch_id": scope, "file_urls": [f"https://storage.mineru.test/upload/{scope}"]}
    elif kind == "mineru_put":
        return httpx.Response(status)
    elif kind == "mineru_poll":
        data = {
            "extract_result": [
                {
                    "data_id": scope,
                    "file_name": remote["filename"],
                    "state": action.get("state", "done" if remote["uploaded"] else "waiting-file"),
                    "full_zip_url": f"https://storage.mineru.test/download/{scope}",
                }
            ]
        }
    else:
        return httpx.Response(status, content=package(action.get("package", "safe")))
    return httpx.Response(status, json={"code": 0, "data": data})


def gateway_factory(settings):
    from backend.infrastructure.rag.mineru_client import MinerUClient

    return MinerUClient(settings, transport=httpx.MockTransport(mineru_transport))


class ControlledPort:
    def __init__(self, original, kind):
        self.original, self.kind = original, kind

    async def embed(self, texts, *, purpose="document"):
        result = await control(
            "embedding",
            {
                "purpose": purpose,
                "count": len(texts),
                "hash": hashlib.sha256("\n".join(texts).encode()).hexdigest(),
            },
        )
        await self.failure(result["action"])
        values = await self.original.embed(texts, purpose=purpose)
        if result["action"].get("fault") == "empty":
            return ()
        if result["action"].get("fault") == "bad_vector":
            return tuple([float("nan")] * len(v) for v in values)
        return values

    async def rank(self, query, texts):
        result = await control(
            "rerank", {"count": len(texts), "hash": hashlib.sha256(query.encode()).hexdigest()}
        )
        await self.failure(result["action"])
        values = await self.original.rank(query, texts)
        if result["action"].get("fault") == "bad_index":
            return ((len(texts) + 1, 1.0),)
        return values

    async def failure(self, action):
        from backend.application.errors import PermanentTaskError, TransientTaskError

        status = action.get("status", 200)
        if status != 200:
            prefix = "EMBEDDING" if self.kind == "embedding" else "RERANK"
            if status in {401, 403}:
                raise PermanentTaskError(prefix + "_AUTH_FAILED", "合成权限失败")
            raise TransientTaskError(prefix + "_TEMPORARY_UNAVAILABLE", "合成临时服务失败")


def embedding_factory(snapshot):
    from backend.infrastructure.providers.rag_registry import embedding_from_profile

    original = embedding_from_profile(snapshot)  # 先经过生产counter/配置守卫，再装配Mock。
    config = snapshot.get("config", snapshot)
    if config.get("adapter_kind", "mock") != "mock":
        raise ValueError("LOCAL_REAL_PROFILE_FORBIDDEN")
    return ControlledPort(original, "embedding")


def rerank_factory(snapshot):
    from backend.infrastructure.providers.rag_registry import rerank_from_profile

    original = rerank_from_profile(snapshot)
    if snapshot.get("config", snapshot).get("adapter_kind", "mock") != "mock":
        raise ValueError("LOCAL_REAL_PROFILE_FORBIDDEN")
    return ControlledPort(original, "rerank")
