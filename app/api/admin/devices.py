from fastapi import APIRouter

from app.api.deps import AdminDep, SessionDep
from app.schemas.admin_devices import DeviceAssignRequest, DeviceAssignResponse
from app.services.admin_devices import AdminDeviceService

router = APIRouter(prefix="/devices", tags=["admin-devices"])


@router.post("/assign", response_model=DeviceAssignResponse)
async def assign_device(
    body: DeviceAssignRequest,
    session: SessionDep,
    admin: AdminDep,
) -> DeviceAssignResponse:
    device = await AdminDeviceService(session).assign(body, admin_id=admin.id)
    return DeviceAssignResponse.model_validate(device)
