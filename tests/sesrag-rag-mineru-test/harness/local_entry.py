"""local专用组合根；真实Compose禁止挂载或启动此模块。"""

import asyncio
import hashlib
import json
import os
import sys

from harness.transport_fixtures import (
    SCOPE,
    control,
    embedding_factory,
    gateway_factory,
    rerank_factory,
)


def install():
    if os.environ.get("TEST_LANE") != "local":
        raise RuntimeError("LOCAL_ENTRY_LANE_REJECTED")
    from backend.application import rag_run_execution, retrieval, session_execution
    from backend.db.rag_models import IndexBuildModel
    from backend.workers import runtime
    from backend.workers.handlers import retrieval_diagnostic_handler
    from backend.workers.handlers.index_build_handler import process_index_build_task

    original_retrieval = retrieval.execute_retrieval
    original_model_factory = session_execution.provider_from_snapshot2

    class ObservedModel:
        def __init__(self, provider):
            self.provider = provider

        async def stream_request(self, request):
            await control(
                "model_request",
                {
                    "messages": [
                        {
                            "role": m.role,
                            "chars": len(m.content),
                            "sha256": hashlib.sha256(m.content.encode()).hexdigest(),
                        }
                        for m in request.messages
                    ]
                },
            )
            async for delta in self.provider.stream_request(request):
                yield delta

    def observed_model_factory(snapshot):
        return ObservedModel(original_model_factory(snapshot))

    async def controlled_retrieval(*args, **kwargs):
        return await original_retrieval(
            *args, **kwargs, embedding_factory=embedding_factory, rerank_factory=rerank_factory
        )

    async def controlled_build(*args, **kwargs):
        factory, _, task_id, _, _ = args[:5]
        from backend.db.models import TaskModel

        async with factory() as session:
            task = await session.get(TaskModel, task_id)
            build = await session.get(IndexBuildModel, task.index_batch_id)
            stage = build.stage
        if stage == "publish":
            await control("before_publish")
        return await process_index_build_task(
            *args, **kwargs, provider_factory=embedding_factory, gateway_factory=gateway_factory
        )

    original_dispatch = runtime.WorkerRuntime._dispatch

    async def dispatch(self, task):
        token = SCOPE.set(f"{task.task_id}:{task.generation}")
        try:
            return await original_dispatch(self, task)
        finally:
            SCOPE.reset(token)

    retrieval.execute_retrieval = controlled_retrieval
    rag_run_execution.execute_retrieval = controlled_retrieval
    retrieval_diagnostic_handler.execute_retrieval = controlled_retrieval
    runtime.process_index_build_task = controlled_build
    runtime.WorkerRuntime._dispatch = dispatch
    session_execution.provider_from_snapshot2 = observed_model_factory
    if not all(
        (
            rag_run_execution.execute_retrieval is controlled_retrieval,
            retrieval_diagnostic_handler.execute_retrieval is controlled_retrieval,
            runtime.process_index_build_task is controlled_build,
            session_execution.provider_from_snapshot2 is observed_model_factory,
        )
    ):
        raise RuntimeError("LOCAL_BINDING_SELFTEST_FAILED")
    identity = {
        "lane": "local",
        "mineru": "production-client+MockTransport",
        "embedding": "guarded-MockPort",
        "rerank": "guarded-MockPort",
        "generation": "explicit-Profile+dummy-HTTP-SSE",
        "dns_tls_proven": False,
        "product_writes": False,
    }
    print(json.dumps({"local_bindings": identity}), flush=True)
    return identity


if __name__ == "__main__":
    install()
    if sys.argv[1] == "api":
        import uvicorn

        uvicorn.run("backend.app:app", host="0.0.0.0", port=8000)
    elif sys.argv[1] == "worker":
        from backend.workers.main import main

        asyncio.run(main())
    else:
        raise ValueError("UNKNOWN_LOCAL_ROLE")
