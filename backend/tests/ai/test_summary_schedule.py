from datetime import UTC, datetime, timedelta

from app.ai.summary import next_attempt

NOW = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)
DEBOUNCE = timedelta(seconds=15)


def test_a_summary_with_no_edit_and_no_wait_can_generate_now() -> None:
    assert next_attempt(None, None, DEBOUNCE) is None


def test_an_edit_waits_out_the_debounce() -> None:
    assert next_attempt(NOW, None, DEBOUNCE) == NOW + DEBOUNCE


def test_a_rate_limit_waits_only_for_the_provider() -> None:
    assert next_attempt(None, NOW + timedelta(seconds=20), DEBOUNCE) == NOW + timedelta(seconds=20)


def test_an_edit_during_a_rate_limit_waits_for_whichever_is_later() -> None:
    late_retry = NOW + timedelta(seconds=30)
    early_retry = NOW + timedelta(seconds=5)

    assert next_attempt(NOW, late_retry, DEBOUNCE) == late_retry
    assert next_attempt(NOW, early_retry, DEBOUNCE) == NOW + DEBOUNCE
