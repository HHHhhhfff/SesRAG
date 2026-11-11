"""构建期按锁定Playwright清单续传官方浏览器包，再由原安装器验证安装。"""

import base64
import hashlib
import http.client
import os
import re
import subprocess
import threading
import time
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def fetch(url, target, deadline):
    # TLS元数据与包CRC共同核对；断流保留部分文件，禁止把部分包当成功。
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as response:
        size = int(response.headers["Content-Length"])
        etag = response.headers.get("ETag")
        hashes = response.headers.get("x-goog-hash", "")
    if not 0 < size < 250 * 1024**2:
        raise ValueError("BROWSER_PACKAGE_SIZE_INVALID")
    checksum = next(
        (v.strip()[4:] for v in hashes.split(",") if v.strip().startswith("md5=")), None
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(12):
        if time.monotonic() > deadline:
            raise TimeoutError("BROWSER_DOWNLOAD_DEADLINE")
        offset = target.stat().st_size if target.exists() else 0
        if offset > size:
            target.unlink()
            offset = 0
        if offset == size:
            try:
                with zipfile.ZipFile(target) as package:
                    if package.testzip() is not None:
                        raise ValueError("BROWSER_ZIP_CRC_INVALID")
                if checksum:
                    with target.open("rb") as source:
                        actual = base64.b64encode(
                            hashlib.file_digest(source, "md5").digest()
                        ).decode()
                    if actual != checksum:
                        raise ValueError("BROWSER_PACKAGE_CHECKSUM_INVALID")
                return
            except (ValueError, zipfile.BadZipFile):
                target.unlink()
                continue
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        if etag and offset:
            headers["If-Range"] = etag
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=30
            ) as response:
                partial = response.status == 206 and response.headers.get(
                    "Content-Range", ""
                ).startswith(f"bytes {offset}-")
                if offset and not partial:
                    raise ValueError("BROWSER_RESUME_RANGE_NOT_HONORED")
                with target.open("ab" if offset else "wb") as output:
                    while block := response.read(256 * 1024):
                        previous = output.tell()
                        output.write(block)
                        if output.tell() // (10 * 1024**2) != previous // (10 * 1024**2):
                            print(f"浏览器包下载进度 {output.tell()}/{size}", flush=True)
                        if output.tell() > size or time.monotonic() > deadline:
                            raise TimeoutError("BROWSER_DOWNLOAD_DEADLINE_OR_SIZE")
            print(f"浏览器包下载进度 {target.stat().st_size}/{size}", flush=True)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            # 只输出错误种类和进度，不输出代理配置；有限重试并保持原版本。
            print(f"浏览器包续传重试 {attempt + 1}: {type(exc).__name__}", flush=True)
            if isinstance(exc, ValueError):
                target.unlink(missing_ok=True)
            time.sleep(min(2**attempt, 10))
    raise ValueError("BROWSER_DOWNLOAD_RETRIES_EXHAUSTED")


def main():
    environment = dict(os.environ)
    environment.pop("PLAYWRIGHT_DOWNLOAD_HOST", None)
    dry = subprocess.check_output(
        ["npx", "playwright", "install", "--dry-run", "--only-shell", "chromium"],
        env=environment,
        text=True,
        timeout=30,
    )
    urls = re.findall(r"Download url:\s+(https://\S+)", dry)
    if not urls or any(urlsplit(url).hostname != "cdn.playwright.dev" for url in urls):
        raise ValueError("PLAYWRIGHT_OFFICIAL_MANIFEST_INVALID")
    packages = {}
    deadline = time.monotonic() + 2400
    for url in urls:
        path = urlsplit(url).path
        target = Path("/cache/browsers/downloads") / hashlib.sha256(url.encode()).hexdigest()
        fetch(url, target, deadline)
        packages[path] = target
        # Playwright的DOWNLOAD_HOST覆盖使用相对builds路径，不含官方主镜像的dbazure前缀。
        if path.startswith("/dbazure/download/playwright/"):
            packages[path.removeprefix("/dbazure/download/playwright")] = target

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            target = packages.get(urlsplit(self.path).path)
            if target is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(target.stat().st_size))
            self.end_headers()
            with target.open("rb") as source:
                while block := source.read(1024**2):
                    self.wfile.write(block)

        def log_message(self, *_):
            pass

    # 回环服务只用于构建期交给官方安装器解包、生成安装标记，不进入运行镜像服务。
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    environment["PLAYWRIGHT_DOWNLOAD_HOST"] = f"http://127.0.0.1:{server.server_port}"
    try:
        subprocess.run(
            ["npx", "playwright", "install", "--only-shell", "chromium"],
            env=environment,
            check=True,
            timeout=180,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
