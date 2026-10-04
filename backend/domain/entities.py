from dataclasses import dataclass

from backend.domain.enums import RunState, TaskState


class InvalidTransitionError(ValueError):
    """表示领域状态机不允许当前状态转移。"""


_RUN_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.QUEUED: {RunState.RUNNING, RunState.CANCELLED},
    RunState.RUNNING: {
        RunState.RETRY_WAITING,
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.RETRY_WAITING: {RunState.RUNNING, RunState.CANCELLED, RunState.FAILED},
    RunState.SUCCEEDED: set(),
    RunState.FAILED: set(),
    RunState.CANCELLED: set(),
}

_TASK_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.QUEUED: {TaskState.LEASED, TaskState.CANCELLED},
    TaskState.LEASED: {
        TaskState.RUNNING,
        TaskState.RETRY_WAITING,
        TaskState.CANCELLED,
        TaskState.FAILED,
    },
    TaskState.RUNNING: {
        TaskState.SUCCEEDED,
        TaskState.RETRY_WAITING,
        TaskState.CANCELLED,
        TaskState.FAILED,
    },
    TaskState.RETRY_WAITING: {TaskState.QUEUED, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.SUCCEEDED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
}


def transition_run(current: RunState, target: RunState) -> RunState:
    if target not in _RUN_TRANSITIONS[current]:
        raise InvalidTransitionError(f"Run cannot transition from {current} to {target}")
    return target


def transition_task(current: TaskState, target: TaskState) -> TaskState:
    if target not in _TASK_TRANSITIONS[current]:
        raise InvalidTransitionError(f"Task cannot transition from {current} to {target}")
    return target


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    seq: int
    text: str
    start_offset: int
    end_offset: int
