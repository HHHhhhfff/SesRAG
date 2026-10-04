from backend.infrastructure.queue.postgres_queue import retry_delay_seconds


def test_retry_delay_is_bounded_exponential():
    assert retry_delay_seconds(1, 2) == 2
    assert retry_delay_seconds(2, 2) == 4
    assert retry_delay_seconds(4, 2) == 16
