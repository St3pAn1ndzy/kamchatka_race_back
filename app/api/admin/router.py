"""Административный API.

Префикс: /api/v1/admin

ВАЖНО: глобальную зависимость require_admin НЕ ставим, потому что
эндпоинт логина (POST /auth/login) должен быть доступен без токена.
Каждый защищённый эндпоинт добавляет Depends(require_admin) явно.

SOS и служебные данные трекеров - только здесь, не в публичном API.
"""

from fastapi import APIRouter

from app.api.admin import auth, devices, directory, equipment, marks, race, stage_route

admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

admin_router.include_router(auth.router)
admin_router.include_router(equipment.router)
admin_router.include_router(devices.router)
admin_router.include_router(race.router)
admin_router.include_router(directory.router)
admin_router.include_router(stage_route.router)
admin_router.include_router(marks.router)
