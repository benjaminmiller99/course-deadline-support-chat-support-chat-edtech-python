from datetime import datetime, timedelta, timezone

from edtech_support.deadline_routing import DeadlineState, classify_deadline


def test_deadline_inside_48_hours_is_due_soon() -> None:
    observed_at = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
    deadline_at = observed_at + timedelta(hours=47, minutes=59)

    assert classify_deadline(deadline_at, observed_at) is DeadlineState.DUE_SOON


def test_past_deadline_is_overdue() -> None:
    observed_at = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
    deadline_at = observed_at - timedelta(seconds=1)

    assert classify_deadline(deadline_at, observed_at) is DeadlineState.OVERDUE
