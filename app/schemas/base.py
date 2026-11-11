"""Базовая Pydantic-схема.

`hide_input_in_errors=True` — Pydantic не включает `input` в ошибки
валидации. Это основная защита от утечки launch_params, паролей
и персональных данных через ответы об ошибках.

Все схемы проекта должны наследоваться от BaseSchema.
"""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        hide_input_in_errors=True,
        from_attributes=True,
    )
