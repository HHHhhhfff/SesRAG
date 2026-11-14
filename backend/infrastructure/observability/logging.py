"""清洗和编码先于入队；stdout阻塞仅影响一个daemon消费者。"""

import logging
import queue
import sys
import threading

from backend.infrastructure.observability.sanitization import encode_record


class SafeLogger:
    def __init__(self, service, environment, stream=None, on_error=None):
        self.service, self.environment = service, environment
        self.stream = stream or sys.stdout
        self.on_error = on_error or (lambda reason: None)
        self.queue = queue.Queue(maxsize=1024)
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._write, daemon=True, name="obs-logs")
        self.thread.start()

    def emit(self, action, **fields):
        if self.stopped.is_set():
            return
        try:
            line = encode_record(self.service, self.environment, action, fields)
            self.queue.put_nowait(line)
        except queue.Full:
            self.on_error("queue_full")
        except Exception:
            self.on_error("handler_error")

    def _write(self):
        while not self.stopped.is_set() or not self.queue.empty():
            try:
                line = self.queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                self.stream.write(line)
                self.stream.flush()
            except Exception:
                self.on_error("handler_error")
            finally:
                self.queue.task_done()

    def close(self, timeout=1):
        self.stopped.set()
        self.thread.join(max(0, timeout))
        return not self.thread.is_alive()


def suppress_library_logs():
    # 不调用getMessage；SDK警告可能含响应、URL或凭据。
    for name in ("httpx", "httpcore", "opentelemetry", "urllib3", "uvicorn", "sqlalchemy"):
        logger = logging.getLogger(name)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
        logger.setLevel(logging.CRITICAL + 1)
        for child_name, child in logging.Logger.manager.loggerDict.items():
            if child_name.startswith(name + ".") and isinstance(child, logging.Logger):
                child.handlers = [logging.NullHandler()]
                child.propagate = False
                child.setLevel(logging.CRITICAL + 1)
