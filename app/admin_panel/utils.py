"""Утилиты для админ-панели."""

from starlette.requests import Request


def get_int_param(request: Request, name: str) -> int | None:
    """Возвращает int-параметр из query string или None.

    Используется в list_query для фильтрации, где параметр может
    отсутствовать, быть пустым или содержать мусор.
    """
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None
