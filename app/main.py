import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import ValidationError
from sqladmin import Admin
from sqlalchemy import create_engine
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from app.admin_panel import VIEWS
from app.admin_panel.admin_auth import AdminPanelAuth
from app.api.admin.router import admin_router
from app.api.errors import (
    pydantic_validation_exception_handler,
    replace_default_validation_error_schema,
    request_validation_exception_handler,
)
from app.api.health import router as health_router
from app.api.middleware import LoggingMiddleware, RequestIDMiddleware
from app.api.v1.router import api_router
from app.config import get_settings
from app.db.base import async_engine
from app.logging_setup import setup_logging

logger = logging.getLogger("avacha")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Avacha API starting up")
    yield
    await async_engine.dispose()
    admin_engine = getattr(app.state, "admin_engine", None)
    if admin_engine is not None:
        admin_engine.dispose()
    logger.info("Avacha API shut down")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)

    app = FastAPI(
        title="Avacha Race — VK Mini App backend",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # SQLAdmin использует cookie-сессию для входа в админ-панель
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.ADMIN_PANEL_SESSION_SECRET,
        same_site="lax",
        https_only=not settings.DEBUG,
    )
    # Порядок: сначала внутренние, потом внешние. CORS — последним.
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Обработчики ошибок валидации (убирают input и ctx из ответа).
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)

    # Роутеры.
    app.include_router(health_router)
    app.include_router(api_router)
    app.include_router(admin_router)

    # SQLAdmin на синхронном движке.
    admin_engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True)
    app.state.admin_engine = admin_engine

    @app.get("/admin-panel", include_in_schema=False)
    @app.get("/admin-panel/", include_in_schema=False)
    async def redirect_to_dashboard():
        return RedirectResponse(url="/admin-panel/dashboard")

    # SQLAdmin на синхронном движке, доступ закрыт через AdminPanelAuth
    admin = Admin(
        app,
        engine=admin_engine,
        base_url="/admin-panel",
        title="Авача — админ панель",
        templates_dir="app/templates",
        authentication_backend=AdminPanelAuth(secret_key=settings.ADMIN_PANEL_SESSION_SECRET),
    )
    for view in VIEWS:
        admin.add_view(view)

    # Безопасная схема ошибок в OpenAPI (без input/ctx).
    replace_default_validation_error_schema(app)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health", "/docs", "/openapi.json"],
        inprogress_name="avacha_http_requests_inprogress",
        inprogress_labels=True,
    ).instrument(app).expose(
        app,
        include_in_schema=False,
        endpoint="/metrics",
    )

    return app


app = create_app()
