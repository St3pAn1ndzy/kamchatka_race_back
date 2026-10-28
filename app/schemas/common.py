"""Общие типы для query-параметров API."""

import re
from typing import Annotated

from pydantic import AwareDatetime, BeforeValidator

_ISO_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _reject_unix_timestamps(v):
    """Pydantic v2 в Python mode коэрсит числовые строки в Unix timestamp.
    Для query-параметров это нежелательно — принимаем только ISO 8601.

    Пример: ?published_to=0.5 → ValueError → 422.
    Пример: ?published_to=2027-03-01T00:00:00Z → passed → AwareDatetime.
    """
    if isinstance(v, str) and not _ISO_DATE_PREFIX.match(v):
        raise ValueError(
            "ожидается дата в формате ISO 8601 (YYYY-MM-DDTHH:MM:SS), "
            "Unix-таймстампы не поддерживаются"
        )
    return v


# Использовать везде, где раньше был AwareDatetime в query-параметрах
QueryDatetime = Annotated[AwareDatetime, BeforeValidator(_reject_unix_timestamps)]
