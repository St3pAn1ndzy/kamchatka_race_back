import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.config import get_settings
from app.db.base import async_session_factory
from app.services.race_demo import RaceDemo
from app.services.scenario_manager import SCENARIOS, apply_scenario

logger = logging.getLogger(__name__)
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
    try:
        await apply_scenario(scenario_name)
        return {"status": "ok", "scenario": scenario_name}
    except ValueError as e:
        # Перехватываем ошибку "Сценарий не найден"
        raise HTTPException(status_code=400, detail=str(e)) from e


async def run_demo_movement(device_id: int, steps: int):
    """Фоновая задача для движения трекера"""
    demo = None
    async with async_session_factory() as session:
        try:
            demo = await RaceDemo.prepare(session, device_id)
            logger.info(f"Запуск движения для трекера {device_id}")

            # Волков уже на 65% пути, начинаем оттуда
            start_ratio = 0.65
            end_ratio = 1.0

            for step in range(steps):
                # Интерполируем от 65% до 100%
                progress = start_ratio + ((end_ratio - start_ratio) * (step / (steps - 1)))
                await demo.tick(progress, sos=False)
                await session.commit()
                await demo.invalidate_cache()
                await asyncio.sleep(3)  # Пауза 3 секунды между точками

        except Exception as e:
            logger.error(f"Ошибка демо-движения: {e}")
        finally:
            if demo:
                # ВАЖНО: Если раскомментировать строку ниже, Волков вернется на стартовую позицию после демо
                # await demo.cleanup()

                # Если оставить закомментированным, он останется на финише (для демо это круче)
                await session.commit()
                await demo.invalidate_cache()
                logger.info("Демо-движение завершено.")


@router.post("/move/{device_id}", dependencies=[Depends(verify_dev_mode)])
async def start_demo_movement(device_id: int, background_tasks: BackgroundTasks, steps: int = 15):
    """Запускает фоновое движение указанного трекера (для показа)"""
    background_tasks.add_task(run_demo_movement, device_id, steps)
    return {"status": "movement_started", "device_id": device_id}
