from fastapi import APIRouter

from app.api.service import scenarios

service_router = APIRouter(prefix="/api/v1/dev", tags=["dev-service"])

service_router.include_router(scenarios.router)
