"""Расчёт свежести последней координаты трекера"""

from datetime import datetime


def get_freshness_status(
    last_message_at: datetime | None,
    *,
    now: datetime,
    interval_seconds: int,
    stale_missed_intervals: int,
) -> str:
    """Проверка на свежесть последней координаты трекера"""
    if interval_seconds < 1:
        raise ValueError("Интервал трекера должен быть положительным")
    if stale_missed_intervals < 2:
        raise ValueError("Порог stale должен быть не меньше двух интервалов")

    if last_message_at is None:
        return "no_signal"

    age_seconds = max(0.0, (now - last_message_at).total_seconds())

    if age_seconds > interval_seconds * stale_missed_intervals:
        return "stale"
    if age_seconds > interval_seconds:
        return "delayed"
    return "fresh"
