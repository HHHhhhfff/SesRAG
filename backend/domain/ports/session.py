"""会话路径端口；应用层负责路径与分叉业务校验。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class BranchRecord:
    branch_id: str
    thread_id: str
    parent_branch_id: str | None
    fork_message_id: str | None
    name: str
    is_default: bool
    head_message_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PathMessage:
    message_id: str
    thread_id: str
    branch_id: str
    seq: int
    role: str


@dataclass(frozen=True)
class PathSegment:
    branch_id: str
    through_seq: int | None


@dataclass(frozen=True)
class BranchPath:
    branches: tuple[BranchRecord, ...]
    segments: tuple[PathSegment, ...]


class BranchRepository(Protocol):
    async def list_branches(self, thread_id: str) -> list[BranchRecord]: ...
    async def get_messages(self, thread_id: str, message_ids: list[str]) -> list[PathMessage]: ...
    async def list_path_messages(
        self,
        thread_id: str,
        segments: tuple[PathSegment, ...],
        *,
        before_seq: int | None = None,
        limit: int | None = None,
        message_id: str | None = None,
    ) -> list[PathMessage]: ...


@dataclass(frozen=True, slots=True)
class ModelProfileRecord:
    profile_id: str
    version: int
    display_name: str
    provider_kind: str
    model_name: str
    generation_params: dict
    base_url: str | None
    context_window_tokens: int
    max_output_tokens: int
    status: str
    is_default: bool
    tokenizer_kind: str
    tokenizer_version: str
    tokenizer_config: dict
    config_ref: str | None


class ModelProfilePort(Protocol):
    async def list_profiles(self) -> list[ModelProfileRecord]: ...
    async def get_profile(self, profile_id: str, version: int) -> ModelProfileRecord | None: ...


@dataclass(frozen=True, slots=True)
class ContextMessage:
    message_id: str
    seq: int
    role: str
    content: str
    status: str
    run_id: str | None
    run_user_message_id: str | None
    run_status: str | None


class ContextRepository(Protocol):
    async def get_candidate_messages(
        self, thread_id: str, message_ids: list[str]
    ) -> list[ContextMessage]: ...
    async def find_reusable_summary(
        self, thread_id: str, branch_id: str, source_hash: str, policy_version: str
    ) -> "ConversationSummaryRecord | None": ...


@dataclass(frozen=True, slots=True)
class ConversationSummaryRecord:
    summary_id: str
    thread_id: str
    branch_id: str
    covered_message_ids: tuple[str, ...]
    from_seq: int
    to_seq: int
    source_hash: str
    source_segments: tuple[dict, ...]
    summary_text: str
    summary_policy_version: str
    source_run_id: str


@dataclass(frozen=True, slots=True)
class ContextPlanRecord:
    context_plan_id: str
    run_id: str
    task_id: str
    generation: int
    attempt: int
    thread_id: str
    branch_id: str
    anchor_message_id: str
    selected_message_ids: tuple[str, ...]
    omitted_messages: tuple[dict, ...]
    omitted_ranges: tuple[dict, ...]
    summary_ids: tuple[str, ...]
    selected_evidence: tuple[dict, ...]
    trim_policy_version: str
    counter_version: str
    estimated_input_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    context_window_tokens: int
    status: str
