"""不可信输入在可终止子进程中处理；取消时等待进程退出，避免后台线程继续耗资源。"""

import asyncio
import json
import os
import sys
import weakref
from dataclasses import asdict

from backend.application.errors import ApplicationError, PermanentTaskError
from backend.domain.rag import ChunkDraftV2, NormalizedArtifact, ParsedBlock

MAX_WIRE = 100 * 1024**2
_SLOTS: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)


async def isolated(operation, raw, extension, *, filename="", mime=None, timeout=30):
    loop = asyncio.get_running_loop()
    slot = _SLOTS.setdefault(loop, asyncio.Semaphore(2))
    try:
        await asyncio.wait_for(slot.acquire(), 2)
    except TimeoutError:
        raise ApplicationError("RAG_PROCESSING_BUSY", "文件处理繁忙，请稍后重试", 429) from None
    try:
        return await _isolated(
            operation, raw, extension, filename=filename, mime=mime, timeout=timeout
        )
    finally:
        slot.release()


def restore_artifact(artifact):
    return NormalizedArtifact(
        artifact["text"],
        tuple(
            ParsedBlock(
                **{
                    **b,
                    "heading_path": tuple(b["heading_path"]),
                    "locations": tuple(b["locations"]),
                }
            )
            for b in artifact["blocks"]
        ),
        artifact["protocol"],
        tuple(artifact.get("unsupported", ())),
    )


async def _isolated(operation, raw, extension, *, filename="", mime=None, timeout=30):
    if len(raw) > MAX_WIRE:
        raise PermanentTaskError("ARTIFACT_LIMIT", "处理输入超过上限")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "backend.infrastructure.rag.isolated_processing",
        operation,
        extension,
        filename,
        mime or "",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={
            k: v
            for k, v in os.environ.items()
            if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "PYTHONPATH", "TEMP", "TMP"}
        },
    )

    async def write_input():
        try:
            process.stdin.write(raw)
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            process.stdin.close()

    async def read_output():
        result = bytearray()
        while block := await process.stdout.read(65536):
            result.extend(block)
            if len(result) > MAX_WIRE:
                raise PermanentTaskError("ARTIFACT_LIMIT", "处理输出超过上限")
        return bytes(result)

    try:
        async with asyncio.timeout(timeout):
            _, output = await asyncio.gather(write_input(), read_output())
            await process.wait()
            if process.returncode:
                raise PermanentTaskError("DOCUMENT_PARSE_LIMIT", "处理进程超限或异常退出")
            result = json.loads(output)
            if "error" in result:
                raise ApplicationError(
                    result["error"], "文件处理被安全拒绝", result.get("status", 422)
                )
            if operation == "validate":
                return tuple(result["value"])
            if operation == "chunk":
                return tuple(
                    ChunkDraftV2(
                        **{
                            **value,
                            "block_segments": tuple(value["block_segments"]),
                            "locations": tuple(value["locations"]),
                        }
                    )
                    for value in result["value"]
                )
            artifact = result["value"]
            return NormalizedArtifact(
                artifact["text"],
                tuple(
                    ParsedBlock(
                        **{
                            **b,
                            "heading_path": tuple(b["heading_path"]),
                            "locations": tuple(b["locations"]),
                        }
                    )
                    for b in artifact["blocks"]
                ),
                artifact["protocol"],
                tuple(artifact["unsupported"]),
            )
    except TimeoutError:
        raise PermanentTaskError("DOCUMENT_PARSE_LIMIT", "文件处理达到时间上限") from None
    except (ValueError, KeyError, TypeError):
        raise PermanentTaskError("DOCUMENT_PARSE_FAILED", "处理结果不符合内部协议") from None
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


def main():
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    try:
        raw = sys.stdin.buffer.read(MAX_WIRE + 1)
        if len(raw) > MAX_WIRE:
            raise PermanentTaskError("ARTIFACT_LIMIT", "输入超限")
        operation, extension, filename, mime = sys.argv[1:5]
        if operation == "validate":
            from backend.infrastructure.rag.office_validation import validate_source

            value = validate_source(filename, mime or None, raw)
        elif operation == "text":
            from backend.infrastructure.rag.local_structure import parse_text

            value = asdict(parse_text(raw, extension))
        elif operation == "package":
            from backend.infrastructure.rag.mineru_outputs import normalize_package

            value = asdict(normalize_package(raw, extension))
        elif operation == "chunk":
            from backend.infrastructure.rag.structured_chunker import split_artifact

            artifact = restore_artifact(json.loads(raw))
            value = [asdict(chunk) for chunk in split_artifact(artifact, **json.loads(filename))]
        else:
            raise ValueError()
        result = {"value": value}
    except ApplicationError as exc:
        result = {"error": exc.code, "status": exc.status_code}
    except Exception:
        result = {"error": "DOCUMENT_PARSE_FAILED", "status": 422}
    output = json.dumps(result, ensure_ascii=False).encode()
    if len(output) > MAX_WIRE:
        output = b'{"error":"ARTIFACT_LIMIT","status":422}'
    sys.stdout.buffer.write(output)


if __name__ == "__main__":
    main()
