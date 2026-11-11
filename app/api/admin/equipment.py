"""Состояние оборудования в административном API"""

from fastapi import APIRouter

from app.api.deps import AdminDep, SessionDep
from app.schemas.admin_equipment import EquipmentHealthResponse
from app.services.admin_equipment import AdminEquipmentService

router = APIRouter(prefix="/equipment", tags=["admin-equipment"])


@router.get("/health", response_model=EquipmentHealthResponse)
async def equipment_health(
    session: SessionDep,
    _admin: AdminDep,
) -> EquipmentHealthResponse:
    """Возвращаем состояние всех трекеров для админки"""
    service = AdminEquipmentService(session)
    return await service.get_health()
