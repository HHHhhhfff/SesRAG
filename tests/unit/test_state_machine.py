from backend.domain.entities import InvalidTransitionError, transition_run, transition_task
from backend.domain.enums import RunState, TaskState


def test_run_retry_waiting_returns_to_running_after_backoff():
    assert transition_run(RunState.RUNNING, RunState.RETRY_WAITING) is RunState.RETRY_WAITING
    assert transition_run(RunState.RETRY_WAITING, RunState.RUNNING) is RunState.RUNNING


def test_run_cannot_return_from_terminal_state():
    try:
        transition_run(RunState.SUCCEEDED, RunState.RUNNING)
    except InvalidTransitionError:
        pass
    else:
        raise AssertionError("terminal Run must not transition back to running")


def test_task_retry_waiting_returns_to_queued():
    assert transition_task(TaskState.RUNNING, TaskState.RETRY_WAITING) is TaskState.RETRY_WAITING
    assert transition_task(TaskState.RETRY_WAITING, TaskState.QUEUED) is TaskState.QUEUED
