"""纯上下文预算与确定性摘要算法；不依赖 ORM 或 Provider。"""

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MessageInput:
    message_id: str
    seq: int
    role: str
    content: str
    run_user_message_id: str | None = None
    run_status: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    document_id: str
    chunk_id: str
    score: float
    text: str
    index_batch_id: str = ""
    start_offset: int = 0
    end_offset: int = 0
    content_hash: str = ""


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class SourceSegment:
    message_id: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class ExtractedSummary:
    text: str
    covered_message_ids: tuple[str, ...]
    source_segments: tuple[SourceSegment, ...]
    source_hash: str
    policy_version: str = "trim_then_extract_v1"


@dataclass(frozen=True, slots=True)
class OmittedRange:
    from_seq: int
    to_seq: int
    count: int
    reason: str


@dataclass(frozen=True, slots=True)
class ContextInput:
    thread_id: str
    branch_id: str
    anchor_message_id: str
    current_input: str
    system_prompt: str
    context_window_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    history: tuple[MessageInput, ...]
    evidence: tuple[EvidenceInput, ...]
    summary_max_tokens: int = 512
    max_candidate_messages: int = 200
    max_candidate_chars: int = 200_000
    prior_omitted_ranges: tuple[OmittedRange, ...] = ()


@dataclass(frozen=True, slots=True)
class MandatoryBudgetCheck:
    status: str
    estimated_input_tokens: int
    available_input_tokens: int
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ContextPlan:
    status: str
    provider_messages: tuple[ModelMessage, ...]
    selected_message_ids: tuple[str, ...]
    omitted_messages: tuple[tuple[str, str], ...]
    omitted_evidence: tuple[tuple[str, str, str], ...]
    omitted_ranges: tuple[OmittedRange, ...]
    selected_evidence: tuple[EvidenceInput, ...]
    selected_evidence_ids: tuple[tuple[str, str], ...]
    summary: ExtractedSummary | None
    estimated_input_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    context_window_tokens: int
    counter_version: str
    failure_reason: str | None = None
    effective_policy_version: str = "trim_then_extract_v1"
    summary_failure_reason: str | None = None


class TokenCounter(Protocol):
    version: str

    def count_text(self, text: str) -> int: ...
    def count_messages(self, messages: tuple[ModelMessage, ...]) -> int: ...


def check_mandatory_budget(request: ContextInput, counter: TokenCounter) -> MandatoryBudgetCheck:
    """Check the prompt and current input before callers load retrieval evidence."""
    if (
        min(request.context_window_tokens, request.reserved_output_tokens) <= 0
        or request.safety_margin_tokens < 0
        or request.reserved_output_tokens + request.safety_margin_tokens
        >= request.context_window_tokens
    ):
        return MandatoryBudgetCheck("budget_exceeded", 0, 0, "CONTEXT_TOO_LARGE")
    mandatory = (
        ModelMessage("system", request.system_prompt),
        ModelMessage("user", request.current_input),
    )
    estimated = counter.count_messages(mandatory)
    available = (
        request.context_window_tokens
        - request.reserved_output_tokens
        - request.safety_margin_tokens
    )
    if estimated > available:
        return MandatoryBudgetCheck("budget_exceeded", estimated, available, "CONTEXT_TOO_LARGE")
    return MandatoryBudgetCheck("ready", estimated, available)


async def load_context_candidates(
    branch_repository,
    content_repository,
    *,
    thread_id: str,
    branch_id: str,
    anchor_message_id: str,
    current_input: str,
):
    """按 Task 2 路径接口读取最多 200 条候选，不重复加入当前输入。"""
    from backend.application.branches import resolve_scope
    from backend.application.errors import ApplicationError

    scope = await resolve_scope(branch_repository, thread_id, branch_id)
    anchor_rows = await branch_repository.list_path_messages(
        thread_id, scope.segments, message_id=anchor_message_id, limit=1
    )
    if not anchor_rows or anchor_rows[0].role != "user":
        raise ApplicationError("INVALID_BRANCH_PATH", "上下文锚点不在当前路径", 422)
    candidates = await branch_repository.list_path_messages(
        thread_id, scope.segments, before_seq=anchor_rows[0].seq + 1, limit=200
    )
    rows = await content_repository.get_candidate_messages(
        thread_id, [row.message_id for row in candidates if row.message_id != anchor_message_id]
    )
    by_id = {row.message_id: row for row in rows}
    result = []
    for candidate in candidates:
        if candidate.message_id == anchor_message_id:
            continue
        message = by_id.get(candidate.message_id)
        if message is None or message.role not in {"user", "assistant"}:
            continue
        if message.role == "assistant" and message.status != "completed":
            continue
        result.append(
            MessageInput(
                message.message_id,
                message.seq,
                message.role,
                message.content,
                message.run_user_message_id,
                message.run_status,
            )
        )
    return tuple(result)


def plan_context(
    request: ContextInput, counter: TokenCounter, *, summarize: bool = True
) -> ContextPlan:
    """先验证 mandatory，再按证据分数和完整历史单元收缩输入。"""
    precheck = check_mandatory_budget(request, counter)
    if precheck.status != "ready":
        return ContextPlan(
            "budget_exceeded",
            (),
            (),
            (),
            (),
            (),
            (),
            (),
            None,
            precheck.estimated_input_tokens,
            request.reserved_output_tokens,
            request.safety_margin_tokens,
            request.context_window_tokens,
            counter.version,
            precheck.failure_reason,
        )
    system = ModelMessage("system", request.system_prompt)
    current = ModelMessage("user", request.current_input)
    available = precheck.available_input_tokens

    candidate_limit = max(0, request.max_candidate_messages)
    history = list(request.history[-candidate_limit:]) if candidate_limit else []
    answered_inputs = {m.run_user_message_id for m in history if m.role == "assistant"}
    # user.run_id 是不可变创建者；后续成功 retry 的 assistant 可完成同一输入轮次。
    excluded = {
        m.message_id
        for m in history
        if m.role == "user"
        and m.run_status in {"failed", "cancelled"}
        and m.message_id not in answered_inputs
    }
    by_input = {
        m.message_id: m for m in history if m.role == "user" and m.message_id not in excluded
    }
    assistant_for: dict[str, MessageInput] = {
        m.run_user_message_id: m
        for m in history
        if m.role == "assistant" and m.run_user_message_id in by_input
    }
    units: list[tuple[MessageInput, ...]] = []
    paired_assistants: set[str] = set()
    for message in history:
        if message.role != "user":
            continue
        if message.message_id in excluded:
            continue
        assistant = assistant_for.get(message.message_id)
        if assistant:
            units.append((message, assistant))
            paired_assistants.add(assistant.message_id)
        else:
            units.append((message,))
    omitted: list[tuple[str, str]] = [
        (message.message_id, "outside_candidate_window")
        for message in request.history[: max(0, len(request.history) - candidate_limit)]
    ]
    omitted_evidence: list[tuple[str, str, str]] = []
    omitted.extend((identity, "incomplete_turn") for identity in sorted(excluded))
    for message in history:
        if message.role == "assistant" and message.message_id not in paired_assistants:
            omitted.append((message.message_id, "incomplete_turn"))
    selected_units = list(units)
    char_count = sum(len(message.content) for unit in selected_units for message in unit)
    while selected_units and char_count > request.max_candidate_chars:
        removed_unit = selected_units.pop(0)
        char_count -= sum(len(message.content) for message in removed_unit)
        omitted.extend((message.message_id, "outside_candidate_window") for message in removed_unit)
    evidence = sorted(request.evidence, key=lambda e: (-e.score, e.document_id, e.chunk_id))

    def messages_for() -> tuple[ModelMessage, ...]:
        ordered = [system]
        for unit in selected_units:
            ordered.extend(ModelMessage(m.role, m.content) for m in unit)
        ordered.append(current)
        for item in evidence:
            ordered.append(ModelMessage("system", "[非可信检索证据]\n" + item.text))
        return tuple(ordered)

    while counter.count_messages(messages_for()) > available and evidence:
        removed = min(evidence, key=lambda e: (e.score, e.document_id, e.chunk_id))
        evidence.remove(removed)
        omitted_evidence.append((removed.document_id, removed.chunk_id, "budget_trimmed"))
    while counter.count_messages(messages_for()) > available and selected_units:
        removed_unit = selected_units.pop(0)
        omitted.extend((m.message_id, "budget_trimmed") for m in removed_unit)
    if counter.count_messages(messages_for()) > available:
        return ContextPlan(
            "budget_exceeded",
            (),
            (),
            tuple(omitted),
            tuple(omitted_evidence),
            (),
            (),
            (),
            None,
            counter.count_messages(messages_for()),
            request.reserved_output_tokens,
            request.safety_margin_tokens,
            request.context_window_tokens,
            counter.version,
            "CONTEXT_TOO_LARGE",
        )

    summary = None
    summary_failure = None
    if summarize and len(selected_units) < len(units):
        removed_ids = {identity for identity, reason in omitted if reason == "budget_trimmed"}
        old_messages = [m for unit in units for m in unit if m.message_id in removed_ids]
        try:
            summary = _extract_summary(
                old_messages, _SummaryCounter(counter), request.summary_max_tokens
            )
        except _SummaryCountFailed as exc:
            raise exc.original from exc
        except Exception:
            summary_failure = "SUMMARY_EXTRACTION_FAILED"
        if summary:
            summary_message = ModelMessage("system", "[非可信历史摘录]\n" + summary.text)
            candidate = (system, summary_message, *messages_for()[1:])
            while counter.count_messages(candidate) > available and selected_units:
                removed_unit = selected_units.pop(0)
                omitted.extend((m.message_id, "budget_trimmed") for m in removed_unit)
                candidate = (system, summary_message, *messages_for()[1:])
            if counter.count_messages(candidate) <= available:
                # 摘录来源已由 ID/hash 记录，摘要数据不重复声称为原始历史。
                final_messages = candidate
            else:
                summary = None
                final_messages = messages_for()
        else:
            final_messages = messages_for()
    else:
        final_messages = messages_for()
    selected_ids = tuple(m.message_id for unit in selected_units for m in unit)
    summarized_ids = set(summary.covered_message_ids) if summary else set()
    omitted_messages = tuple(
        (message_id, "summarized" if message_id in summarized_ids else reason)
        for message_id, reason in omitted
        if reason != "outside_candidate_window"
    )
    seq_by_id = {message.message_id: message.seq for message in request.history}
    range_entries = sorted(
        (
            seq_by_id[message_id],
            "summarized" if message_id in summarized_ids else reason,
        )
        for message_id, reason in omitted
        if reason in {"outside_candidate_window", "budget_trimmed"}
    )
    omitted_ranges = (*request.prior_omitted_ranges, *_group_omitted_ranges(range_entries))
    return ContextPlan(
        "ready",
        tuple(final_messages),
        selected_ids,
        omitted_messages,
        tuple(omitted_evidence),
        omitted_ranges,
        tuple(evidence),
        tuple((e.document_id, e.chunk_id) for e in evidence),
        summary,
        counter.count_messages(tuple(final_messages)),
        request.reserved_output_tokens,
        request.safety_margin_tokens,
        request.context_window_tokens,
        counter.version,
        None,
        "trim_then_extract_v1" if summarize and not summary_failure else "trim_only_v1",
        summary_failure,
    )


class _SummaryCountFailed(Exception):
    def __init__(self, original):
        self.original = original


class _SummaryCounter:
    def __init__(self, counter):
        self.counter = counter
        self.version = counter.version

    def count_messages(self, messages):
        return self.counter.count_messages(messages)

    def count_text(self, text):
        try:
            return self.counter.count_text(text)
        except Exception as exc:
            raise _SummaryCountFailed(exc) from exc


def _group_omitted_ranges(entries: list[tuple[int, str]]) -> tuple[OmittedRange, ...]:
    ranges: list[OmittedRange] = []
    for seq, reason in entries:
        if ranges and ranges[-1].reason == reason and ranges[-1].to_seq + 1 == seq:
            previous = ranges[-1]
            ranges[-1] = OmittedRange(previous.from_seq, seq, previous.count + 1, reason)
        else:
            ranges.append(OmittedRange(seq, seq, 1, reason))
    return tuple(ranges)


def _extract_summary(
    messages: list[MessageInput], counter: TokenCounter, maximum: int
) -> ExtractedSummary | None:
    parts: list[str] = []
    segments: list[SourceSegment] = []
    used: list[str] = []
    for message in sorted(messages, key=lambda item: item.seq):
        content = message.content[:128]
        part = f"{message.role}: {content}"
        candidate = "\n".join((*parts, part))
        if counter.count_text(candidate) > maximum:
            break
        parts.append(part)
        used.append(message.message_id)
        segments.append(SourceSegment(message.message_id, 0, len(content)))
    if not parts:
        return None
    source = json.dumps(
        [(m.message_id, m.content) for m in messages if m.message_id in used], ensure_ascii=False
    )
    return ExtractedSummary(
        "\n".join(parts), tuple(used), tuple(segments), hashlib.sha256(source.encode()).hexdigest()
    )
