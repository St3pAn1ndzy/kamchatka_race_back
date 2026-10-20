"""Сервис импорта судейских отметок из CSV.

TODO: Пока здесь заглушка для парсинга. Когда получим реальный CSV,
заменим внутренности parse_csv, а остальная логика (запись в БД) останется.
"""

import logging
from datetime import datetime

logger = logging.getLogger("avacha.import")


def parse_csv(file_content: bytes, stage_start_time: datetime, stage_number: int) -> list[dict]:
    """
    ЗАГЛУШКА.
    Должна возвращать список словарей в формате:
    [
        {"number": 14, "type": "start", "time": datetime, "status": "OK"},
        {"number": 14, "type": "finish", "time": datetime, "status": "OK"},
        {"number": 51, "type": "start", "time": datetime, "status": "WITHDRAWN"},
    ]
    """
    logger.info(f"Запущен парсинг CSV (заглушка). Размер файла: {len(file_content)} байт.")

    # ВРЕМЕННАЯ ЗАГЛУШКА (чтобы можно было протестировать UI)
    return [
        {"number": 14, "type": "start", "time": stage_start_time, "status": "OK"},
        {
            "number": 14,
            "type": "finish",
            "time": stage_start_time.replace(hour=12, minute=39, second=55),
            "status": "OK",
        },
    ]
