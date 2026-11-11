"""Глобальные обработчики ошибок валидации.

Задача: не светить `input` и `ctx` в ответах и в логах.
`input` может содержать launch_params (с sign), пароли, тексты фидбека.
`ctx` может содержать объекты исключений с пользовательскими данными.

Основная защита — `BaseSchema.hide_input_in_errors=True` (убирает input
на уровне Pydantic). Обработчики ниже — страховка на уровне FastAPI.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger("avacha.validation")


def _clean_errors(errors: list[dict]) -> list[dict]:
    """Оставляет только безопасные поля: loc, msg, type."""
    return [
        {
            "loc": list(err.get("loc", [])),
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in errors
    ]


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = _clean_errors(exc.errors())

    logger.warning(
        "request_validation_error",
        extra={
            "request_id": getattr(request.state, "request_id", "-"),
            "path": request.url.path,
            "method": request.method,
            "error_count": len(errors),
            "error_locs": [e["loc"] for e in errors],
        },
    )

    return JSONResponse(status_code=422, content={"detail": errors})


async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    errors = _clean_errors(exc.errors())

    logger.warning(
        "pydantic_validation_error",
        extra={
            "request_id": getattr(request.state, "request_id", "-"),
            "path": request.url.path,
            "method": request.method,
            "error_count": len(errors),
            "error_locs": [e["loc"] for e in errors],
        },
    )

    return JSONResponse(status_code=422, content={"detail": errors})


def replace_default_validation_error_schema(app: FastAPI) -> None:
    """Заменяет схему HTTPValidationError в OpenAPI.

    FastAPI по умолчанию показывает в /docs поля `input` и `ctx` в схеме
    ошибки валидации. Заменяем на безопасную — только loc, msg, type.
    """

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )

        components = schema.get("components", {}).get("schemas", {})
        if "HTTPValidationError" in components:
            components["HTTPValidationError"] = {
                "type": "object",
                "properties": {
                    "detail": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/ValidationError"},
                    }
                },
                "title": "HTTPValidationError",
            }
        if "ValidationError" in components:
            components["ValidationError"] = {
                "type": "object",
                "properties": {
                    "loc": {
                        "type": "array",
                        "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                        "title": "Location",
                    },
                    "msg": {"type": "string", "title": "Message"},
                    "type": {"type": "string", "title": "Error Type"},
                },
                "required": ["loc", "msg", "type"],
                "title": "ValidationError",
            }

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
