"""Настройка логирования приложения.

Форматтер ExtraFormatter дописывает в конец строки все поля, переданные
через `logger.info(..., extra={...})`.

Пример вывода:
    2026-10-16 12:34:56 INFO [avacha.access] request request_id=abc123 \
method=GET path=/api/v1/stages status=200 duration_ms=12.4
"""

import json
import logging
from typing import Any

from app.config import Settings

# Стандартные поля LogRecord. Всё, что вне этого набора, считаем extras.
_STANDARD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "taskName",
}

_DEFAULT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


# Ключи, значения которых нельзя логировать ни при каких условиях.
# 152-ФЗ + launch_params VK (sign, vk_*) + auth.
_FORBIDDEN_EXTRA_KEYS = {
    "body",
    "input",
    "ctx",
    "request_body",
    "response_body",
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "sign",
    "secret",
    "cookie",
    "authorization",
    "vk_user_id",
    "vk_app_id",
    "launch_params",
}

_REDACTED = "<redacted>"


def _fmt_value(value: Any) -> str:
    """Списки и словари — компактным JSON без пробелов."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


class ExtraFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {}
        for k, v in record.__dict__.items():
            if k in _STANDARD_ATTRS:
                continue
            if k.lower() in _FORBIDDEN_EXTRA_KEYS:
                extras[k] = _REDACTED
            else:
                extras[k] = v
        if not extras:
            return base
        suffix = " ".join(f"{k}={_fmt_value(v)}" for k, v in extras.items())
        return f"{base} {suffix}"


def _make_extra_handler() -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(ExtraFormatter(_DEFAULT_FORMAT))
    return handler


def _make_plain_handler() -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
    return handler


def setup_logging(settings: Settings) -> None:
    """Единая настройка логирования: root + uvicorn.

    - root — с ExtraFormatter, чтобы extra-поля из middleware и
      обработчиков ошибок попадали в вывод;
    - uvicorn — отдельными handler'ами без extras-суффиксов,
      иначе его логи получат хвост `request_id=- method=- path=-`.
    """
    level = logging.DEBUG if settings.DEBUG else logging.INFO

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(_make_extra_handler())
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = False
        uv_logger.addHandler(_make_plain_handler())
        uv_logger.setLevel(level)
