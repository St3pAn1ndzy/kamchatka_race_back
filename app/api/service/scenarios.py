from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.services.scenario_manager import SCENARIOS, apply_scenario

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def verify_dev_mode():
    settings = get_settings()
    if settings.ENV != "dev":
        raise HTTPException(status_code=403, detail="Service endpoints disabled in production")
    return True


@router.get("/", dependencies=[Depends(verify_dev_mode)])
async def list_scenarios():
    """Возвращает список доступных сценариев для кнопок во фронте"""
    return {"scenarios": list(SCENARIOS.keys())}


@router.post("/{scenario_name}", dependencies=[Depends(verify_dev_mode)])
async def switch_scenario(scenario_name: str):
    """Переключает состояние приложения на указанный сценарий"""

    await apply_scenario(scenario_name)
    return {"status": "ok", "scenario": scenario_name}
