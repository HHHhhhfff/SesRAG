"""选入计划顺序必须同时约束持久投影和最终引用。"""

from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.application.context import ContextInput, EvidenceInput, plan_context
from backend.application.rag_run_execution import BundleContext
from backend.application.session_execution import ordered_plan_evidence, publish_plan
from backend.db.models import ContextPlanModel
from backend.db.rag_models import ContextEvidenceModel
from tests.unit.test_context_planning import Counter


@pytest.mark.asyncio
@pytest.mark.parametrize("window", [200, 36])
async def test_published_plan_components_and_citation_inputs_follow_final_order(
    monkeypatch, window
):
    import backend.application.session_execution as module

    def bundle(doc, identity, score, text):
        return BundleContext(
            identity,
            doc,
            "batch",
            "safe.md",
            text,
            0,
            len(text),
            score,
            (),
            None,
            (
                {
                    "component_id": identity + "-part",
                    "start_offset": 0,
                    "end_offset": len(text),
                    "content_hash": "hash",
                },
            ),
            score,
        )

    evidence = [
        bundle("z", "low", 0.1, "L" * 150),
        bundle("b", "second", 0.9, "second"),
        bundle("a", "first", 0.9, "first"),
    ]
    request = ContextInput("t", "b", "u", "q", "s", window, 1, 0, (), (), number_evidence=True)
    request = replace(
        request,
        evidence=tuple(
            EvidenceInput(e.document_id, e.bundle_id, e.score, e.text) for e in evidence
        ),
    )
    plan = plan_context(request, Counter(), summarize=False)
    added = []
    session = SimpleNamespace(add=added.append, flush=AsyncMock(), commit=AsyncMock())

    @asynccontextmanager
    async def factory():
        yield session

    task = SimpleNamespace(lease_expires_at=None, deadline_at=None, attempt=2)
    run = SimpleNamespace(
        execution_schema_version=3, run_id="r", thread_id="t", branch_id="b", user_message_id="u"
    )
    monkeypatch.setattr(module, "lock_execution", AsyncMock(return_value=(task, run)))
    monkeypatch.setattr(module, "append_event", AsyncMock())
    monkeypatch.setattr(module, "check_locked_times", lambda *args: None)
    monkeypatch.setattr(module, "plan_summary", lambda row: {})
    await publish_plan(factory, "task", "worker", 2, plan, request, {}, evidence)
    row = next(item for item in added if isinstance(item, ContextPlanModel))
    projected = [item["bundle_id"] for item in row.selected_evidence]
    expected = [identity for _, identity in plan.selected_evidence_ids]
    assert projected == expected
    assert [item.component_id for item in added if isinstance(item, ContextEvidenceModel)] == [
        identity + "-part" for identity in expected
    ]
    assert [e.bundle_id for e in ordered_plan_evidence(plan, evidence)] == expected
    assert "[S1]" in plan.provider_messages[2].content
