from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum


class DeadlineState(StrEnum):
    ROUTINE = "routine"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"


def classify_deadline(deadline_at: datetime, observed_at: datetime) -> DeadlineState:
    remaining = deadline_at.astimezone(timezone.utc) - observed_at.astimezone(timezone.utc)
    if remaining.total_seconds() < 0:
        return DeadlineState.OVERDUE
    if remaining <= timedelta(hours=48):
        return DeadlineState.DUE_SOON
    return DeadlineState.ROUTINE

