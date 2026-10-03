"""Административный API.

Префикс: /api/v1/admin

ВАЖНО: глобальную зависимость require_admin НЕ ставим, потому что
эндпоинт логина (POST /auth/login) должен быть доступен без токена.
Каждый защищённый эндпоинт добавляет Depends(require_admin) явно.

SOS и служебные данные трекеров - только здесь, не в публичном API.
"""

from fastapi import APIRouter

from app.api.admin import auth, equipment, race

admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

admin_router.include_router(auth.router)
admin_router.include_router(race.router)
admin_router.include_router(equipment.router)

# По мере готовности:
#
# from app.api.admin import race, marks, equipment, notifications, stats
#
# admin_router.include_router(marks.router)
# admin_router.include_router(notifications.router)
# admin_router.include_router(stats.router)
