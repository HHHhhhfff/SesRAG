"""解析隔离入口；stdout 仅返回有界 DTO 或安全错误码。"""

import json
import sys
from pathlib import Path

from backend.application.errors import ApplicationError
from backend.infrastructure.rag.parsers import parser_result


def main():
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    try:
        result = parser_result(Path(sys.argv[1]), sys.argv[2])
    except ApplicationError as exc:
        result = {"error": exc.code, "retryable": exc.retryable}
    except Exception:
        result = {"error": "DOCUMENT_PARSE_FAILED", "retryable": False}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
