"""Базовый класс для всех ModelView в админ-панели."""

from sqladmin import ModelView
from starlette.requests import Request


class BaseAdminView(ModelView):
    """Общие настройки для всех моделей.

    По умолчанию:
    - 25 строк на страницу (с выбором до 200).
    - Удаление ЗАПРЕЩЕНО (включаем точечно для мусорных моделей).
    - Экспорт ВЫКЛЮЧЕН (включаем точечно для нужных).
    """

    page_size = 25
    page_size_options = [25, 50, 100, 200]
    can_delete = False
    can_export = False

    async def _parse_pks(self, request: Request) -> list[int]:
        """Разбирает ID из запроса SQLAdmin (поддерживает формат '1,2,3')."""
        raw_pks = request.query_params.getlist("pks")
        pks = [pk.strip() for raw in raw_pks for pk in raw.split(",") if pk.strip()]
        return [int(pk) for pk in pks]
