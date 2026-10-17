import pytest
from pydantic import ValidationError

from backend.config import Settings


@pytest.mark.parametrize(
    "values",
    [
        {"vector_dimension": 128},
        {"task_lease_ttl": 0},
        {"task_heartbeat_interval": -1},
        {"task_max_attempts": 0},
        {"task_retry_base_delay": 0},
        {"task_deadline": 0},
        {"worker_shutdown_grace": 0},
        {"queue_poll_interval": 0},
        {"sse_poll_interval": -1},
        {"rag_top_k": 0},
        {"chunk_size": 0},
        {"chunk_overlap": -1},
        {"task_heartbeat_interval": 30, "task_lease_ttl": 30},
        {"chunk_overlap": 800, "chunk_size": 800},
    ],
)
def test_invalid_configuration_is_rejected_before_database_use(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_zero_chunk_overlap_is_valid():
    assert Settings(_env_file=None, chunk_overlap=0).chunk_overlap == 0
