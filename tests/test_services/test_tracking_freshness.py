from datetime import UTC, datetime, timedelta

import pytest

from app.services.tracking_freshness import get_freshness_status

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("age_seconds", "expected"),
    [
        (0, "fresh"),
        (1200, "fresh"),
        (1201, "delayed"),
        (2400, "delayed"),
        (2401, "stale"),
    ],
)
def test_freshness_boundaries(age_seconds: int, expected: str) -> None:
    result = get_freshness_status(
        NOW - timedelta(seconds=age_seconds),
        now=NOW,
        interval_seconds=1200,
        stale_missed_intervals=2,
    )
    assert result == expected


def test_no_signal() -> None:
    result = get_freshness_status(
        None,
        now=NOW,
        interval_seconds=1200,
        stale_missed_intervals=2,
    )
    assert result == "no_signal"
