"""Демонстрация движения и SOS на локальной базе без обращения к Iridium"""

import argparse
import asyncio
import signal

from app.config import get_settings
from app.db.base import async_engine, async_session_factory
from app.services.cache import cache
from app.services.race_demo import RaceDemo, check_demo_settings


async def run(args: argparse.Namespace) -> None:
    """Выполняет ограниченный сценарий и очищает свои точки при остановке"""
    check_demo_settings(get_settings())
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        async with async_session_factory() as session:
            demo = await RaceDemo.prepare(session, args.device_id)
            print(
                f"ДЕМО: трекер {args.device_id}, участник {demo.assignment[0]}, "
                f"этап {demo.assignment[1]}, запуск {demo.run_id}",
                flush=True,
            )
            print("Ускоренное движение по маршруту, это не данные живого Iridium", flush=True)
            try:
                for step in range(args.steps):
                    point = await demo.tick(step / (args.steps - 1), sos=step >= args.sos_at)
                    await session.commit()
                    await demo.invalidate_cache()
                    print(
                        f"Шаг {step}: {point.lat:.6f}, {point.lon:.6f}, "
                        f"SOS={'ВКЛ' if step >= args.sos_at else 'выкл'}",
                        flush=True,
                    )
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=args.interval)
                        break
                    except TimeoutError:
                        pass
            finally:
                await session.rollback()
                await demo.cleanup()
                await session.commit()
                await demo.invalidate_cache()
                print("Демоточки удалены, исходное состояние трекера восстановлено", flush=True)
    finally:
        await cache.close()
        await async_engine.dispose()


def main() -> None:
    """Проверяет параметры демонстрации до подключения к базе"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", type=int, required=True, help="ID локального демотрекера")
    parser.add_argument("--steps", type=int, default=24, help="Количество обновлений от 2 до 600")
    parser.add_argument("--interval", type=float, default=5, help="Пауза от 1 до 60 секунд")
    parser.add_argument("--sos-at", type=int, default=6, help="Шаг включения SOS, начиная с нуля")
    args = parser.parse_args()
    if not (
        args.device_id > 0
        and 2 <= args.steps <= 600
        and 1 <= args.interval <= 60
        and 0 <= args.sos_at < args.steps
    ):
        parser.error("Проверьте ID, число шагов, интервал и шаг SOS")
    try:
        asyncio.run(run(args))
    except ValueError as exc:
        parser.exit(1, f"Демонстрация не запущена: {exc}\n")


if __name__ == "__main__":
    main()
