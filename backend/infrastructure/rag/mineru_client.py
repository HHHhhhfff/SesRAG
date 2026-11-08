"""MinerU精准API原件上传；未知提交绝不自动重复申请batch。"""

from backend.application.errors import PermanentTaskError, TransientTaskError
from backend.infrastructure.rag.download_safety import SafeHTTP, decode_json

API = "https://mineru.net/api/v4"


class MinerUClient:
    def __init__(self, settings, *, transport=None):
        self.secret = settings.mineru_api_key
        self.api = SafeHTTP(["mineru.net"], transport=transport)
        hosts = [h.strip() for h in settings.mineru_storage_host_allowlist.split(",") if h.strip()]
        self.storage = SafeHTTP(hosts, transport=transport)

    @staticmethod
    def checked(status, raw):
        if status in {401, 403}:
            raise PermanentTaskError("MINERU_AUTH_FAILED", "MinerU认证失败")
        if status == 429:
            raise PermanentTaskError("MINERU_QUOTA_EXHAUSTED", "MinerU额度或频率受限")
        if status >= 500:
            raise TransientTaskError("MINERU_TEMPORARY_UNAVAILABLE", "MinerU暂不可用")
        body = decode_json(raw, "MINERU_OUTPUT_UNSUPPORTED")
        if status != 200 or body.get("code") != 0 or not isinstance(body.get("data"), dict):
            raise PermanentTaskError("MINERU_PARSE_FAILED", "MinerU拒绝或无法处理请求")
        return body["data"]

    async def submit(self, job):
        c = job["config"]
        try:
            status, raw = await self.api.request(
                "POST",
                API + "/file-urls/batch",
                headers={"Authorization": f"Bearer {self.secret}"},
                json_body={
                    "files": [
                        {
                            "name": job["filename"],
                            "data_id": job["parse_job_id"],
                            "is_ocr": c["is_ocr"],
                        }
                    ],
                    "model_version": c["model_version"],
                    "enable_table": c["enable_table"],
                    "enable_formula": c["enable_formula"],
                    "language": c["language"],
                },
            )
        except TransientTaskError:
            raise PermanentTaskError(
                "MINERU_SUBMISSION_UNKNOWN", "申请结果未知，不能自动重新提交"
            ) from None
        if status >= 500:
            raise PermanentTaskError("MINERU_SUBMISSION_UNKNOWN", "申请结果未知，不能自动重新提交")
        try:
            data = self.checked(status, raw)
        except PermanentTaskError as exc:
            if exc.code == "MINERU_OUTPUT_UNSUPPORTED":
                raise PermanentTaskError(
                    "MINERU_SUBMISSION_UNKNOWN", "申请应答损坏，不自动重提"
                ) from None
            raise
        try:
            if (
                not isinstance(data["batch_id"], str)
                or not 1 <= len(data["batch_id"]) <= 200
                or len(data["file_urls"]) != 1
            ):
                raise ValueError()
            self.storage.validate(data["file_urls"][0])
            return {
                "batch_id": data["batch_id"],
                "upload_url": data["file_urls"][0],
                "parse_job_id": job["parse_job_id"],
                "filename": job["filename"],
            }
        except (KeyError, TypeError, ValueError):
            raise PermanentTaskError(
                "MINERU_SUBMISSION_UNKNOWN", "申请身份不完整，不能自动重新提交"
            ) from None

    async def upload(self, content, handle):
        status, _ = await self.storage.request(
            "PUT", handle["upload_url"], content=content, timeout=120
        )
        if status not in {200, 201, 204}:
            raise TransientTaskError("MINERU_UPLOAD_UNCONFIRMED", "上传未确认，请先查询原batch")

    async def poll(self, handle):
        status, raw = await self.api.request(
            "GET",
            API + "/extract-results/batch/" + handle["batch_id"],
            headers={"Authorization": f"Bearer {self.secret}"},
        )
        data = self.checked(status, raw)
        try:
            rows = data["extract_result"]
            if len(rows) != 1 or not isinstance(rows[0], dict):
                raise ValueError()
            row = rows[0]
            if (
                row.get("data_id") != handle["parse_job_id"]
                or row.get("file_name") != handle["filename"]
            ):
                raise ValueError()
            state = row["state"]
            if state not in {"waiting-file", "pending", "running", "converting", "done", "failed"}:
                raise ValueError()
            # 只返回安全状态／受保护能力，原始错误消息不持久化或回显。
            result = {"state": state}
            if state == "done":
                self.storage.validate(row["full_zip_url"])
                result["download_url"] = row["full_zip_url"]
            progress = row.get("extract_progress")
            if isinstance(progress, dict):
                result["progress"] = {
                    k: progress[k]
                    for k in ("extracted_pages", "total_pages")
                    if type(progress.get(k)) is int and 0 <= progress[k] <= 100000
                }
            return result
        except (KeyError, TypeError, ValueError):
            raise PermanentTaskError("MINERU_OUTPUT_UNSUPPORTED", "解析状态协议不支持") from None

    async def download(self, handle):
        status, raw = await self.storage.request(
            "GET", handle["download_url"], max_bytes=100 * 1024**2, timeout=120
        )
        if status != 200:
            raise PermanentTaskError("MINERU_RESULT_UNAVAILABLE", "MinerU结果不可用")
        return raw
