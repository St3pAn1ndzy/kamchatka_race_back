"""Middleware: request_id и логирование запросов.

Не логируем тело и чувствительные заголовки — только метод, путь,
статус и время. Тело может содержать launch_params и персональные данные.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("avacha.access")

# Заголовки, которые нельзя писать в логи.
_SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Генерирует X-Request-ID и кладёт его в request.state."""

    HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(self.HEADER) or uuid.uuid4().hex[:16]
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[self.HEADER] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Логирует метод, путь, статус и длительность запроса."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        request_id = getattr(request.state, "request_id", "-")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
