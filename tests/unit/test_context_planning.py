from dataclasses import dataclass

import backend.application.context as context_module
from backend.application.context import (
    ContextInput,
    EvidenceInput,
    MessageInput,
    plan_context,
)
from backend.infrastructure.providers.context_counter import MockTokenCounter


@dataclass(frozen=True)
class Counter:
    version = "test-counter@1"

    def count_text(self, text: str) -> int:
        return len(text)

    def count_messages(self, messages) -> int:
        return sum(len(item.content) + 1 for item in messages)


def test_tied_lowest_evidence_eviction_uses_ascending_document_chunk_identity():
    request = ContextInput(
        "t",
        "b",
        "u",
        "q",
        "s",
        27,
        1,
        0,
        (),
        (
            EvidenceInput("b", "c", 0.5, "123456"),
            EvidenceInput("a", "c", 0.5, "123456"),
        ),
    )
    plan = plan_context(request, Counter(), summarize=False)
    assert plan.omitted_evidence == (("a", "c", "budget_trimmed"),)
    assert plan.selected_evidence_ids == (("b", "c"),)


def test_summary_counter_failure_is_not_hidden_as_extraction_fallback():
    import pytest

    class BrokenCounter(Counter):
        def count_text(self, text):
            raise RuntimeError("counter unavailable")

    request = ContextInput(
        "t", "b", "u", "q", "s", 30, 1, 0, (MessageInput("old", 1, "user", "old " * 20),), ()
    )
    with pytest.raises(RuntimeError, match="counter unavailable"):
        plan_context(request, BrokenCounter())


def test_mandatory_budget_check_counts_only_system_and_current_input():
    request = ContextInput(
        thread_id="t",
        branch_id="b",
        anchor_message_id="current",
        current_input="question",
        system_prompt="system",
        context_window_tokens=21,
        reserved_output_tokens=3,
        safety_margin_tokens=2,
        history=(MessageInput("old", 1, "user", "must not be counted"),),
        evidence=(EvidenceInput("d", "c", 1.0, "must not be counted"),),
    )

    check_mandatory_budget = getattr(context_module, "check_mandatory_budget", None)
    assert callable(check_mandatory_budget)
    check = check_mandatory_budget(request, Counter())

    assert check.status == "ready"
    assert check.estimated_input_tokens == len("system") + 1 + len("question") + 1
    assert check.available_input_tokens == 16


def test_mandatory_over_budget_fails_before_candidate_or_evidence_use():
    request = ContextInput(
        thread_id="t",
        branch_id="b",
        anchor_message_id="current",
        current_input="123456",
        system_prompt="system",
        context_window_tokens=10,
        reserved_output_tokens=2,
        safety_margin_tokens=1,
        history=(),
        evidence=(EvidenceInput("d", "c", 1.0, "evidence"),),
    )
    plan = plan_context(request, Counter())
    assert plan.status == "budget_exceeded"
    assert plan.provider_messages == ()
    assert plan.selected_evidence == ()


def test_history_trimming_removes_whole_old_turns_and_prunes_low_score_evidence_first():
    request = ContextInput(
        thread_id="t",
        branch_id="b",
        anchor_message_id="current",
        current_input="q",
        system_prompt="s",
        context_window_tokens=60,
        reserved_output_tokens=3,
        safety_margin_tokens=1,
        history=(
            MessageInput("u1", 1, "user", "old question " * 4),
            MessageInput("a1", 2, "assistant", "old answer " * 4, run_user_message_id="u1"),
            MessageInput("u2", 3, "user", "new question"),
            MessageInput("a2", 4, "assistant", "new answer", run_user_message_id="u2"),
        ),
        evidence=(),
    )
    plan = plan_context(request, Counter(), summarize=False)
    assert "u1" not in plan.selected_message_ids and "a1" not in plan.selected_message_ids
    assert [item.content for item in plan.provider_messages][-1] == "q"
    assert plan.omitted_ranges[0].reason == "budget_trimmed"


def test_candidate_window_omissions_are_reported_as_compact_ranges():
    request = ContextInput(
        thread_id="t",
        branch_id="b",
        anchor_message_id="current",
        current_input="q",
        system_prompt="s",
        context_window_tokens=1000,
        reserved_output_tokens=3,
        safety_margin_tokens=1,
        history=(
            MessageInput("u0", 1, "user", "old"),
            MessageInput("a0", 2, "assistant", "answer", run_user_message_id="u0"),
            MessageInput("u1", 3, "user", "kept"),
            MessageInput("a1", 4, "assistant", "answer", run_user_message_id="u1"),
        ),
        evidence=(),
        max_candidate_messages=2,
    )

    plan = plan_context(request, Counter(), summarize=False)

    assert [
        (item.from_seq, item.to_seq, item.count, item.reason) for item in plan.omitted_ranges
    ] == [(1, 2, 2, "outside_candidate_window")]
    assert ("u0", "outside_candidate_window") not in plan.omitted_messages


def test_low_score_evidence_is_removed_before_higher_score_evidence():
    request = ContextInput(
        thread_id="t",
        branch_id="b",
        anchor_message_id="current",
        current_input="q",
        system_prompt="s",
        context_window_tokens=50,
        reserved_output_tokens=3,
        safety_margin_tokens=1,
        history=(),
        evidence=(
            EvidenceInput("d2", "c2", 0.1, "low" * 3),
            EvidenceInput("d1", "c1", 0.9, "high" * 3),
        ),
    )
    plan = plan_context(request, Counter(), summarize=False)
    assert ("d1", "c1") in plan.selected_evidence_ids
    assert ("d2", "c2") not in plan.selected_evidence_ids


def test_summary_records_only_extracted_source_segments_and_hash():
    request = ContextInput(
        thread_id="t",
        branch_id="b",
        anchor_message_id="current",
        current_input="q",
        system_prompt="s",
        context_window_tokens=180,
        reserved_output_tokens=3,
        safety_margin_tokens=1,
        history=(
            MessageInput("u1", 1, "user", "A" * 300),
            MessageInput("a1", 2, "assistant", "answer", run_user_message_id="u1"),
        ),
        evidence=(),
        summary_max_tokens=200,
    )
    plan = plan_context(request, Counter())
    assert plan.summary is not None
    assert plan.summary.covered_message_ids == ("u1", "a1")
    assert plan.summary.source_segments[0].end_offset == 128
    assert len(plan.summary.source_hash) == 64


def test_mock_counter_has_stable_non_character_quarter_boundaries():
    counter = MockTokenCounter()
    assert counter.count_text("abcd") == 1
    assert counter.count_text("你🙂") == 2


def test_candidate_message_window_keeps_exactly_latest_200_facts():
    history = tuple(MessageInput(f"m{i}", i, "user", "x") for i in range(1, 202))
    request = ContextInput("t", "b", "current", "q", "s", 10000, 10, 0, history, ())
    plan = plan_context(request, Counter(), summarize=False)
    assert len(plan.selected_message_ids) == 200
    assert plan.selected_message_ids[0] == "m2"
    assert plan.selected_message_ids[-1] == "m201"
    assert plan.omitted_ranges[0].from_seq == plan.omitted_ranges[0].to_seq == 1
    assert plan.omitted_ranges[0].reason == "outside_candidate_window"


def test_candidate_character_limit_accepts_200000_and_trims_at_200001():
    def plan(first_length):
        history = (
            MessageInput("m1", 1, "user", "a" * first_length),
            MessageInput("m2", 2, "user", "b" * 100_000),
        )
        request = ContextInput("t", "b", "current", "q", "s", 1_000_000, 10, 0, history, ())
        return plan_context(request, Counter(), summarize=False)

    exact = plan(100_000)
    overflow = plan(100_001)
    assert exact.selected_message_ids == ("m1", "m2")
    assert overflow.selected_message_ids == ("m2",)
    assert overflow.omitted_ranges[0].reason == "outside_candidate_window"
