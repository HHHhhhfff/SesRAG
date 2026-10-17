"""FE持久浏览器入口：复用5a唯一控制器，仅增加固定失败Port。"""

import importlib.util
from pathlib import Path

import uvicorn
from pg_harness import ChildWorker

spec = importlib.util.spec_from_file_location(
    "worker_controller", Path(__file__).with_name("worker-controller.py")
)
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


def worker_factory(harness, stage):
    return ChildWorker(
        harness,
        stage,
        "frontend-bootstrap.py" if stage == "failure" else "worker-bootstrap.py",
    )


if __name__ == "__main__":
    uvicorn.run(
        controller.controller_app(
            controller.create_database(),
            worker_factory=worker_factory,
            stages=("embed", "model", "delta", "production", "failure"),
            # FE_014：本project Redis独立逻辑库，不受主Worker的ready键影响。
            harness_options={"redis_enabled": True, "redis_url": "redis://redis:6379/15"},
        ),
        host="0.0.0.0",
        port=8765,
        log_level="warning",
        access_log=False,
    )
