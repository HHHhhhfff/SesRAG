"""测试工程路径、原子账本与有界命令；不透传开发配置。"""

import hashlib
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
ROOT = SUITE.parents[1] if SUITE.name == "sesrag-rag-mineru-test" else Path("/app")
LABEL = "sesrag.test.suite"
SUITE_NAME = "rag-mineru-003"
RUN_PATTERN = r"rag-[a-z0-9-]{8,80}"
COMMAND_SCRATCH = SUITE / "tmp"
PROCESS_LEDGER = None


class ProcessJob:
    """Windows Job关闭时回收整棵CLI进程树，防止父CLI退出后buildx遗留句柄。"""

    def __init__(self, process):
        self.handle = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("ProcessTime", ctypes.c_longlong),
                ("JobTime", ctypes.c_longlong),
                ("Flags", wintypes.DWORD),
                ("MinWorking", ctypes.c_size_t),
                ("MaxWorking", ctypes.c_size_t),
                ("Active", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("Priority", wintypes.DWORD),
                ("Scheduling", wintypes.DWORD),
            ]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("Basic", BasicLimits),
                ("IO", ctypes.c_ulonglong * 6),
                ("ProcessMemory", ctypes.c_size_t),
                ("JobMemory", ctypes.c_size_t),
                ("PeakProcess", ctypes.c_size_t),
                ("PeakJob", ctypes.c_size_t),
            ]

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = self.kernel.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not handle or not self.kernel.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            raise RuntimeError("PROCESS_JOB_SETUP_FAILED")
        if not self.kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(process._handle))):
            self.kernel.CloseHandle(handle)
            raise RuntimeError("PROCESS_JOB_ASSIGN_FAILED")
        self.handle = handle

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def process_token(pid, include_exited=False):
    try:
        if os.name != "nt":
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            return fields[19] if include_exited or fields[0] != "Z" else None
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        kernel.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            *([ctypes.POINTER(wintypes.FILETIME)] * 4),
        ]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        values = [wintypes.FILETIME() for _ in range(4)]
        try:
            # Windows保留未释放句柄的终止进程对象；创建时间存在不代表进程仍活动。
            status = wintypes.DWORD()
            if not include_exited and (
                not kernel.GetExitCodeProcess(handle, ctypes.byref(status)) or status.value != 259
            ):
                return None
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)):
                return None
            return str(values[0].dwHighDateTime * 2**32 + values[0].dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    except (OSError, IndexError):
        return None


def record_process(pid, remove=False):
    if PROCESS_LEDGER is None:
        return
    values = load(PROCESS_LEDGER) if PROCESS_LEDGER.exists() else []
    values = [row for row in values if row["pid"] != pid]
    if not remove:
        token = process_token(pid, include_exited=True)
        if token is None:
            raise ValueError("PROCESS_IDENTITY_UNAVAILABLE")
        values.append({"pid": pid, "created": token})
    write(PROCESS_LEDGER, values)


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def load(path):
    with Path(path).open("rb") as source:
        raw = source.read(4 * 1024**2 + 1)
    if len(raw) > 4 * 1024**2:
        raise ValueError("JSON_INPUT_LIMIT")
    return json.loads(raw.decode("utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".new")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Windows索引/安全扫描可能短暂占用账本句柄；有界重试仍保留原子替换。
    for attempt in range(8):
        try:
            temp.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.05 * (attempt + 1))


def run_path(area, identity):
    if not re.fullmatch(RUN_PATTERN, identity):
        raise ValueError("INVALID_RUN_ID")
    path = (SUITE / area / identity).resolve()
    if path.parent != (SUITE / area).resolve():
        raise ValueError("UNSAFE_RUN_PATH")
    return path


def child_env(extra=None):
    # Docker/凭据变量全部显式提供；只保留操作系统与CLI正常运行所需项。
    allowed = {
        "PATH",
        "SystemRoot",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "DOCKER_CONFIG",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_CERT_PATH",
        "DOCKER_TLS_VERIFY",
        "SSH_AUTH_SOCK",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "ALL_PROXY",
        "ProgramFiles",
        "ProgramFiles(x86)",
        "CommonProgramFiles",
        "CommonProgramFiles(x86)",
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in {x.upper() for x in allowed}}
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", COMPOSE_ANSI="never")
    env.update(extra or {})
    return env


def terminate_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=15)


def command(args, *, timeout=30, check=True, env=None, output_limit=5 * 1024**2):
    # 用文件接收避免PIPE无界内存；原件仅在本轮tmp，采证再投影。
    import tempfile

    scratch = COMMAND_SCRATCH
    scratch.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="command-", dir=scratch)
    process = None
    job = None
    try:
        with os.fdopen(fd, "wb") as stream:
            process = subprocess.Popen(
                list(map(str, args)),
                cwd=ROOT,
                env=child_env(env),
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
            )
            job = ProcessJob(process)
            record_process(process.pid)
            start = time.monotonic()
            while process.poll() is None:
                if time.monotonic() - start > timeout or Path(name).stat().st_size > output_limit:
                    terminate_tree(process)
                    raise RuntimeError("COMMAND_TIMEOUT_OR_OUTPUT_LIMIT")
                time.sleep(0.1)
        data = Path(name).read_bytes()
        if len(data) > output_limit:
            raise RuntimeError("COMMAND_OUTPUT_LIMIT")
        result = data.decode("utf-8", errors="replace")
        if check and process.returncode:
            # 原始命令可能含DSN，不进入异常；调用方采证必须脱敏。
            raise RuntimeError(f"COMMAND_FAILED_{process.returncode}")
        return process.returncode, result
    finally:
        if process is not None and process.poll() is None:
            terminate_tree(process)
        if job is not None:
            job.close()
        if process is not None:
            record_process(process.pid, remove=True)
        Path(name).unlink(missing_ok=True)


def docker_json(args):
    return json.loads(command(["docker", *args])[1])


def engine_identity():
    return {
        "context": command(["docker", "context", "show"])[1].strip(),
        "daemon": command(["docker", "info", "--format", "{{.ID}}"])[1].strip(),
    }


def schema_check(name, value):
    from jsonschema import Draft202012Validator

    Draft202012Validator(load(SUITE / "schemas" / f"{name}.schema.json")).validate(value)
