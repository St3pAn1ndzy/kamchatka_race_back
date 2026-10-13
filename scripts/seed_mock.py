"""Скрипт для заполнения dev-БД тестовыми данными.

Запуск:
    poetry run python -m scripts.seed_mock
    poetry run python -m scripts.seed_mock --reset
    poetry run python -m scripts.seed_mock --users 50 --no-track
"""

import argparse
import asyncio
import hashlib
import logging
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from app.config import get_settings
from app.db.base import async_session_factory
from app.db.models import (
    AdminAccount,
    AuditLog,
    Checkpoint,
    Device,
    Discipline,
    FanSubscription,
    FAQItem,
    NewsPost,
    NotificationQueue,
    OfficialMark,
    Participant,
    PushSubscription,
    SavedItem,
    ScheduleEvent,
    Season,
    ShareEvent,
    Stage,
    StageRoutePoint,
    TrackPoint,
    User,
    UserFeedback,
    ViewerLocation,
)
from app.enums import (
    CheckpointKind,
    NewsSource,
    NotificationEventType,
    NotificationStatus,
    ParticipantStatus,
    PublicationStatus,
    ScheduleKind,
    StageStatus,
    ViewerLocationKind,
)
from app.security.passwords import hash_password
from app.security.tokens import create_user_token

logger = logging.getLogger("avacha.seed")
settings = get_settings()

# --- Константы seed-данных -------------------------------------------------

SEASON_YEAR = 2027
SEASON_TITLE = "Авача 2027"

# Дисциплины: (code, название)
DISCIPLINES = [
    ("long", "Длинная"),
    ("middle", "Средняя"),
    ("sprint", "Спринт"),
]

# Каюры: (имя, регион)
MUSHERS = [
    ("Алексей Плотников", "Камчатский край"),
    ("Мария Кравцова", "Камчатский край"),
    ("Иван Соболев", "Москва"),
    ("Ольга Романова", "Камчатский край"),
    ("Дмитрий Белов", "Санкт-Петербург"),
    ("Наталья Кузнецова", "Новосибирск"),
    ("Сергей Волков", "Камчатский край"),
    ("Екатерина Морозова", "Хабаровск"),
    ("Андрей Соколов", "Москва"),
    ("Татьяна Лебедева", "Санкт-Петербург"),
    ("Павел Егоров", "Камчатский край"),
    ("Ирина Никитина", "Новосибирск"),
    ("Владимир Фёдоров", "Хабаровск"),
    ("Анна Орлова", "Москва"),
    ("Николай Семёнов", "Камчатский край"),
]

# Этапы: (номер, дистанция, название, дата старта)
STAGES = [
    (
        1,
        100.0,
        "Этап 1. Петропавловск-Камчатский — Налычево",
        datetime(2027, 3, 1, 2, 0, tzinfo=UTC),
    ),
    (2, 120.0, "Этап 2. Налычево — перевал Двойной", datetime(2027, 3, 2, 2, 0, tzinfo=UTC)),
    (3, 80.0, "Этап 3. Перевал Двойной — финиш", datetime(2027, 3, 3, 2, 0, tzinfo=UTC)),
]

# КП на каждом этапе: (code, name, kind, altitude, km от старта гонки)
CHECKPOINTS = [
    ("Старт", "Старт этапа", CheckpointKind.START, 20, 0),
    ("КП-1", "Контрольный пункт у ручья", CheckpointKind.CHECKPOINT, 350, 30),
    ("КП-2", "Контрольный пункт на перевале", CheckpointKind.CHECKPOINT, 700, 70),
    ("Финиш", "Финиш этапа", CheckpointKind.FINISH, 300, 100),
]

# Координаты Камчатки для генерации маршрутов
BASE_LAT = 62.0
BASE_LON = 129.0
LAT_SPREAD = 1.5
LON_SPREAD = 1.5

# Новости
NEWS_TITLES = [
    "Старт «Авачи 2027» — всё готово к началу гонки",
    "Первый этап завершён: результаты и время лидеров",
    "Победитель первого дня — неожиданный рывок",
    "Этап 2: преодоление перевалов Налычево",
    "Финиш гонки позади: итоги «Авачи 2027»",
]

# FAQ: (question, answer, category)
FAQ_ITEMS = [
    (
        "Как добраться до места старта гонки?",
        "До старта в Петропавловске-Камчатском ходят городские автобусы и такси. "
        "Для зрителей на финише этапа организуют трансфер от гостиниц — расписание публикуется в программе.",
        "Транспорт",
    ),
    (
        "Есть ли парковка у места старта?",
        "Да, рядом со стартовой площадкой оборудована бесплатная парковка на 150 мест. "
        "В дни этапов парковка открывается с 07:00.",
        "Транспорт",
    ),
    (
        "Что взять с собой на трассу?",
        "Тёплую одежду, термос с горячим чаем и защиту от ветра. На КП работают пункты обогрева.",
        "Безопасность",
    ),
    (
        "Что делать при экстренной ситуации на трассе?",
        "На каждом контрольном пункте дежурит судья и медицинский работник. "
        "Зрителям нельзя выходить на трассу во время прохождения упряжек.",
        "Безопасность",
    ),
    (
        "Где остановиться в Петропавловске-Камчатском?",
        "В городе работают гостиницы разного уровня, а также хостелы и гостевые дома. "
        "Рекомендуем бронировать заранее — в дни фестиваля спрос высокий.",
        "Проживание",
    ),
]

# Зрительские локации: (name, kind, directions, travel_time, safety)
VIEWER_LOCATIONS = [
    (
        "Старт гонки, Петропавловск-Камчатский",
        ViewerLocationKind.START,
        "От центра города 10 минут на такси или автобусе № 24 до ост. «Гонка».",
        30,
        "Держитесь за ограждения, собак на старте кормить запрещено.",
    ),
    (
        "Финиш этапа 1, Налычево",
        ViewerLocationKind.FINISH,
        "Из города — экскурсионный автобус раз в час, в пути около 1,5 часов.",
        90,
        "Соблюдайте дистанцию до финишного створа, не выходите на лёд реки.",
    ),
    (
        "Смотровая площадка «Перевал Двойной»",
        ViewerLocationKind.VIEWPOINT,
        "На перевал ведёт грунтовая дорога, доступна только на полноприводном автомобиле.",
        45,
        "Край обрыва не огорожен — не подходите близко к кромке.",
    ),
    (
        "Фестивальная площадка «Берингия»",
        ViewerLocationKind.FESTIVAL,
        "Площадка у центрального стадиона, пешком 5 минут от остановки «Стадион».",
        20,
        "Работают пункты обогрева и горячее питание.",
    ),
]


# --- Утилиты ---------------------------------------------------------------


def _random_position(rng: random.Random) -> tuple[float, float]:
    """Случайная точка в районе Камчатки."""
    lat = round(BASE_LAT + rng.uniform(-LAT_SPREAD, LAT_SPREAD), 6)
    lon = round(BASE_LON + rng.uniform(-LON_SPREAD, LON_SPREAD), 6)
    return lat, lon


def _interp_with_offset(
        start_lat: float,
        start_lon: float,
        finish_lat: float,
        finish_lon: float,
        ratio: float,
        offset: float,
) -> tuple[float, float]:
    """Точка на отрезке start→finish с перпендикулярным сдвигом offset (в градусах)."""
    base_lat = start_lat + (finish_lat - start_lat) * ratio
    base_lon = start_lon + (finish_lon - start_lon) * ratio
    d_lat = finish_lat - start_lat
    d_lon = finish_lon - start_lon
    norm = (d_lat ** 2 + d_lon ** 2) ** 0.5 or 1.0
    perp_lat = -d_lon / norm
    perp_lon = d_lat / norm
    return round(base_lat + perp_lat * offset, 6), round(base_lon + perp_lon * offset, 6)


def _dedup_key(imei: str, recorded_at: datetime) -> str:
    """Уникальный ключ для TrackPoint: sha256(imei:recorded_at)."""
    raw = f"{imei}:{recorded_at.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _exists(session, model) -> bool:
    """Есть ли хоть одна запись в таблице (для идемпотентности)."""
    result = await session.execute(select(model.id).limit(1))
    return result.scalar_one_or_none() is not None


async def _count(session, model) -> int:
    """Количество записей в таблице (для сводки)."""
    result = await session.execute(select(model.id))
    return len(result.all())


def _note_created(created: dict[str, int], key: str, amount: int) -> None:
    created[key] = created.get(key, 0) + amount


# --- Основная логика -------------------------------------------------------


async def main(*, reset: bool, users_count: int, no_track: bool, force: bool) -> None:
    """Заполняет dev-БД тестовыми данными. Один commit в конце."""
    # 1. Проверка окружения: сидим только в ENV=dev.
    if settings.ENV != "dev" and not force:
        raise RuntimeError(
            f"Seed разрешён только в ENV=dev, сейчас ENV={settings.ENV!r}. "
            "Для прод-окружения используйте --force."
        )

    if no_track:
        logger.info("--no-track: треки, маршрут и судейские отметки будут пропущены")

    # Воспроизводимый генератор случайных чисел.
    rng = random.Random(2027)

    created: dict[str, int] = {}

    async with async_session_factory() as session:
        # 2. Сброс: TRUNCATE всех таблиц с CASCADE и сбросом последовательностей
        if reset:
            logger.info("Сброс: очищаю таблицы")
            reset_order = [
                # Зависимые от участников/КП/админов
                AuditLog,
                OfficialMark,
                TrackPoint,
                StageRoutePoint,
                Device,
                Checkpoint,
                Stage,
                Discipline,
                Season,
                # Подписки и активность пользователей
                FanSubscription,
                SavedItem,
                ShareEvent,
                NotificationQueue,
                PushSubscription,
                UserFeedback,
                # Основные справочники
                Participant,
                NewsPost,
                ScheduleEvent,
                FAQItem,
                ViewerLocation,
                AdminAccount,
                User,
            ]
            tables = ", ".join(m.__tablename__ for m in reset_order)
            await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

        # 3. Seed по порядку FK.
        now = datetime.now(tz=UTC)

        # --- Season ---
        if not await _exists(session, Season):
            season = Season(
                year=SEASON_YEAR,
                title=SEASON_TITLE,
                starts_at=datetime(2027, 2, 27, tzinfo=UTC),
                ends_at=datetime(2027, 3, 6, tzinfo=UTC),
                is_active=True,
            )
            session.add(season)
            await session.flush()
            _note_created(created, "Season", 1)
        else:
            season = (await session.execute(select(Season).limit(1))).scalar_one_or_none()
            logger.info("Season уже есть — пропускаю")

        # --- Discipline ---
        if not await _exists(session, Discipline):
            disciplines = [
                Discipline(
                    season_id=season.id,
                    code=code,
                    name=name,
                    sort_order=order,
                    is_active=True,
                )
                for order, (code, name) in enumerate(DISCIPLINES)
            ]
            session.add_all(disciplines)
            await session.flush()
            discipline_ids = [d.id for d in disciplines]
            _note_created(created, "Discipline", len(disciplines))
        else:
            disciplines = (
                (await session.execute(select(Discipline).order_by(Discipline.sort_order)))
                .scalars()
                .all()
            )
            discipline_ids = [d.id for d in disciplines]
            logger.info("Discipline уже есть — пропускаю")

        # --- User ---
        if not await _exists(session, User):
            users = []
            for i in range(1, users_count + 1):
                users.append(
                    User(
                        vk_user_id=100000 + i,
                        first_name=f"Болельщик {i}",
                        last_name="",
                        platform="vk",
                        # У половины пользователей разрешены push-уведомления.
                        notifications_allowed=(i % 2 == 0),
                        consent_version="1.0",
                        consent_accepted_at=now - timedelta(days=30),
                        onboarding_passed_at=now - timedelta(days=20),
                    )
                )
            session.add_all(users)
            await session.flush()
            _note_created(created, "User", len(users))
        else:
            users = (await session.execute(select(User).order_by(User.id))).scalars().all()
            logger.info("User уже есть — пропускаю")

        # --- AdminAccount ---
        if not await _exists(session, AdminAccount):
            admin = AdminAccount(
                login="admin",
                password_hash=hash_password("admin123"),
                display_name="Главный администратор",
                is_active=True,
            )
            session.add(admin)
            await session.flush()
            _note_created(created, "AdminAccount", 1)
        else:
            admin = (
                        await session.execute(select(AdminAccount).where(AdminAccount.login == "admin"))
                    ).scalar_one_or_none() or (
                        await session.execute(select(AdminAccount).limit(1))
                    ).scalar_one_or_none()
            logger.info("AdminAccount уже есть — пропускаю")

        # --- Participant ---
        if not await _exists(session, Participant):
            participants = []
            for index, (name, region) in enumerate(MUSHERS):
                participants.append(
                    Participant(
                        name=name,
                        number=index + 1,
                        region=region,
                        discipline_id=discipline_ids[index % len(discipline_ids)],
                        photo_url=None,
                        bio=f"Опытный каюр из региона {region}. Участник гонки «{SEASON_TITLE}».",
                        dogs_count=rng.randint(4, 12),
                        status=ParticipantStatus.REGISTERED.value,
                    )
                )
            session.add_all(participants)
            await session.flush()
            _note_created(created, "Participant", len(participants))
        else:
            participants = (
                (await session.execute(select(Participant).order_by(Participant.number)))
                .scalars()
                .all()
            )
            logger.info("Participant уже есть — пропускаю")

        # --- Stage ---
        if not await _exists(session, Stage):
            stages = [
                Stage(
                    name=name,
                    distance_km=distance,
                    start_time=starts_at,
                    finish_time=starts_at + timedelta(hours=6),
                    order_index=number - 1,
                    tracker_interval_seconds=1200,
                    status=StageStatus.PLANNED.value,
                    results_publication=(
                        PublicationStatus.PROVISIONAL.value
                        if number == 1
                        else PublicationStatus.DRAFT.value
                    ),
                    season_id=season.id,
                    number=number,
                )
                for number, distance, name, starts_at in STAGES
            ]
            session.add_all(stages)
            await session.flush()
            _note_created(created, "Stage", len(stages))
        else:
            stages = (
                (await session.execute(select(Stage).order_by(Stage.order_index))).scalars().all()
            )
            logger.info("Stage уже есть — пропускаю")

        first_stage = stages[0]
        first_admin = admin

        # --- Checkpoint ---
        checkpoints: list[Checkpoint] = []
        if not await _exists(session, Checkpoint):
            # Профиль километража: дистанции этапов накапливаются.
            cumulative_start = 0
            for stage in stages:
                start_lat, start_lon = _random_position(rng)
                finish_lat, finish_lon = _random_position(rng)
                total_km = stage.distance_km
                stage_km_marks = [0, int(total_km * 0.3), int(total_km * 0.7), int(total_km)]
                for order, (code, name, kind, altitude, _) in enumerate(CHECKPOINTS):
                    ratio = order / (len(CHECKPOINTS) - 1)
                    lat = round(start_lat + (finish_lat - start_lat) * ratio, 6)
                    lon = round(start_lon + (finish_lon - start_lon) * ratio, 6)
                    checkpoints.append(
                        Checkpoint(
                            stage_id=stage.id,
                            code=code,
                            name=name,
                            kind=kind.value,
                            description=f"{name} — контроль времени на этапе {stage.number}.",
                            lat=lat,
                            lon=lon,
                            altitude=altitude,
                            km_from_race_start=cumulative_start + stage_km_marks[order],
                            order_index=order,
                            has_judge=True,
                            is_public=True,
                        )
                    )
                cumulative_start += int(total_km)
            session.add_all(checkpoints)
            await session.flush()
            _note_created(created, "Checkpoint", len(checkpoints))
        else:
            checkpoints = (
                (await session.execute(select(Checkpoint).order_by(Checkpoint.id))).scalars().all()
            )
            logger.info("Checkpoint уже есть — пропускаю")

        # Старт и финиш первого этапа — ориентиры для треков.
        # Выбираем по kind, чтобы не зависеть от порядка записей в БД.
        first_stage_cps = sorted(
            (cp for cp in checkpoints if cp.stage_id == first_stage.id),
            key=lambda c: c.order_index,
        )
        path_start = next(cp for cp in first_stage_cps if cp.kind == CheckpointKind.START.value)
        path_finish = next(cp for cp in first_stage_cps if cp.kind == CheckpointKind.FINISH.value)

        # --- Device ---
        if not await _exists(session, Device):
            devices = [
                Device(
                    iridium_number=f"{i:03d}",
                    imei=f"30023456{i:07d}",  # 8 + 7 = 15 цифр
                    name=f"Трекер №{i:03d}",
                    participant_id=participants[i - 1].id,
                    stage_id=first_stage.id,
                    is_active=True,
                    battery_percent=80,
                    sos_active=False,
                    last_message_at=now - timedelta(hours=2),
                )
                for i in range(1, len(participants) + 1)
            ]
            session.add_all(devices)
            await session.flush()
            _note_created(created, "Device", len(devices))
        else:
            devices = (await session.execute(select(Device).order_by(Device.id))).scalars().all()
            logger.info("Device уже есть — пропускаю")

        # --- StageRoutePoint ---
        if not no_track and not await _exists(session, StageRoutePoint):
            # Маршруты всех этапов для карты: по 20 точек на этап.
            route_points: list[StageRoutePoint] = []
            for stage in stages:
                stage_cps = sorted(
                    (cp for cp in checkpoints if cp.stage_id == stage.id),
                    key=lambda c: c.order_index,
                )
                stage_start = next(cp for cp in stage_cps if cp.kind == CheckpointKind.START.value)
                stage_finish = next(
                    cp for cp in stage_cps if cp.kind == CheckpointKind.FINISH.value
                )
                for i in range(20):
                    lat, lon = _interp_with_offset(
                        stage_start.lat,
                        stage_start.lon,
                        stage_finish.lat,
                        stage_finish.lon,
                        i / 19,
                        0.0,
                    )
                    route_points.append(
                        StageRoutePoint(stage_id=stage.id, position=i, lat=lat, lon=lon)
                    )
            session.add_all(route_points)
            await session.flush()
            _note_created(created, "StageRoutePoint", len(route_points))
        elif not no_track:
            logger.info("StageRoutePoint уже есть — пропускаю")

        # --- TrackPoint ---
        track_points: list[TrackPoint] = []
        if not no_track and not await _exists(session, TrackPoint):
            # Скрипт генерирует 20 точек на участника (первый этап).
            points_count = 20
            track_total_km = first_stage.distance_km
            for pi, participant in enumerate(participants):
                if pi >= len(devices):
                    break
                device = devices[pi]
                # Перпендикулярный сдвиг трека — участники не идут по одной линии.
                track_offset = rng.uniform(-0.01, 0.01)
                for j in range(points_count):
                    ratio = j / (points_count - 1)
                    lat, lon = _interp_with_offset(
                        path_start.lat,
                        path_start.lon,
                        path_finish.lat,
                        path_finish.lon,
                        ratio,
                        track_offset,
                    )
                    # Точки каждые 20 минут назад, старт участников сдвинут на 2 минуты.
                    recorded_at = now - timedelta(minutes=20 * (points_count - 1 - j) + 2 * pi)
                    track_points.append(
                        TrackPoint(
                            iridium_point_id=None,
                            deduplication_key=_dedup_key(device.imei, recorded_at),
                            device_id=device.id,
                            participant_id=participant.id,
                            stage_id=first_stage.id,
                            lat=lat,
                            lon=lon,
                            altitude=round(20 + ratio * 100, 1),
                            course_deg=None,
                            source_speed=None,
                            average_speed_kmh=None,
                            km_from_start=round(ratio * track_total_km, 2),
                            recorded_at=recorded_at,
                            is_confirmed=True,
                        )
                    )
            session.add_all(track_points)
            await session.flush()
            _note_created(created, "TrackPoint", len(track_points))
        elif not no_track:
            logger.info("TrackPoint уже есть — пропускаю")
            # Для отметок используем уже существующие точки первого этапа.
            track_points = (
                (
                    await session.execute(
                        select(TrackPoint).where(TrackPoint.stage_id == first_stage.id)
                    )
                )
                .scalars()
                .all()
            )

        # --- OfficialMark ---
        # Судейские отметки: старт и финиш первого этапа для каждого участника.
        if not no_track and not await _exists(session, OfficialMark):
            official_marks: list[OfficialMark] = []
            for participant in participants:
                participant_points = [
                    tp for tp in track_points if tp.participant_id == participant.id
                ]
                if not participant_points:
                    continue
                participant_points.sort(key=lambda tp: tp.recorded_at)
                start_mark = participant_points[0]
                finish_mark = participant_points[-1]
                official_marks.append(
                    OfficialMark(
                        participant_id=participant.id,
                        checkpoint_id=path_start.id,
                        mark_time=start_mark.recorded_at,
                        penalty_minutes=0,
                        mandatory_stop_minutes=0,
                        comment="Отметка старта (сид).",
                        entered_by_admin_id=first_admin.id,
                        is_cancelled=False,
                    )
                )
                official_marks.append(
                    OfficialMark(
                        participant_id=participant.id,
                        checkpoint_id=path_finish.id,
                        mark_time=finish_mark.recorded_at,
                        penalty_minutes=0,
                        mandatory_stop_minutes=0,
                        comment="Отметка финиша этапа (сид).",
                        entered_by_admin_id=first_admin.id,
                        is_cancelled=False,
                    )
                )
            session.add_all(official_marks)
            await session.flush()
            _note_created(created, "OfficialMark", len(official_marks))
        elif not no_track:
            logger.info("OfficialMark уже есть — пропускаю")

        # --- FanSubscription ---
        if not await _exists(session, FanSubscription):
            fan_subscriptions: list[FanSubscription] = []
            user_ids = [u.id for u in users]
            for participant in participants:
                count = rng.randint(5, 10)
                for user_id in rng.sample(user_ids, min(count, len(user_ids))):
                    fan_subscriptions.append(
                        FanSubscription(user_id=user_id, participant_id=participant.id)
                    )
            session.add_all(fan_subscriptions)
            await session.flush()
            _note_created(created, "FanSubscription", len(fan_subscriptions))
        else:
            logger.info("FanSubscription уже есть — пропускаю")

        # --- PushSubscription ---
        if not await _exists(session, PushSubscription):
            push_subscriptions = [
                PushSubscription(
                    user_id=user.id,
                    notifications_enabled=True,
                    subscribed_at=now - timedelta(days=10),
                )
                for user in users
                if user.notifications_allowed
            ]
            session.add_all(push_subscriptions)
            await session.flush()
            _note_created(created, "PushSubscription", len(push_subscriptions))
        else:
            logger.info("PushSubscription уже есть — пропускаю")

        # --- NotificationQueue ---
        if not await _exists(session, NotificationQueue):
            notifications: list[NotificationQueue] = []
            event_types = list(NotificationEventType)
            # По 5 уведомлений: 3 старых SENT + 2 свежих PENDING.
            for user in users:
                if not user.notifications_allowed:
                    continue
                for k in range(5):
                    event_type = event_types[k % len(event_types)]
                    if k < 3:
                        sent_at = now - timedelta(days=2, hours=k)
                        notifications.append(
                            NotificationQueue(
                                user_id=user.id,
                                event_type=event_type.value,
                                title="Ваш каюр в лидерах",
                                body=f"Данные на {sent_at:%H:%M}: участник №{k + 1} прошёл КП-1.",
                                status=NotificationStatus.SENT.value,
                                attempts=1,
                                scheduled_at=sent_at,
                                sent_at=sent_at,
                            )
                        )
                    else:
                        scheduled_at = now + timedelta(hours=k)
                        notifications.append(
                            NotificationQueue(
                                user_id=user.id,
                                event_type=event_type.value,
                                title="Скоро старт этапа",
                                body="Старт следующего этапа через 1 час. Следите за картой.",
                                status=NotificationStatus.PENDING.value,
                                attempts=0,
                                scheduled_at=scheduled_at,
                                sent_at=None,
                            )
                        )
            session.add_all(notifications)
            await session.flush()
            _note_created(created, "NotificationQueue", len(notifications))
        else:
            logger.info("NotificationQueue уже есть — пропускаю")

        # --- NewsPost ---
        if not await _exists(session, NewsPost):
            news_posts = []
            for i, title in enumerate(NEWS_TITLES):
                news_posts.append(
                    NewsPost(
                        title=title,
                        lead=f"Кратко о событиях дня: {title.lower().rstrip('.')}.",
                        body=(
                            f"Подробный репортаж. {title}. "
                            "Следите за обновлениями в официальном сообществе ВКонтакте."
                        ),
                        cover_url=None,
                        source=NewsSource.MANUAL.value,
                        vk_url=None,
                        stage_id=first_stage.id if i < 2 else None,
                        published_at=now - timedelta(days=max(0, 2 - i // 2)),
                        is_published=True,
                        # Одна важная новость — уходит в push-уведомление.
                        is_important=(i == 1),
                        is_pinned=False,
                    )
                )
            session.add_all(news_posts)
            await session.flush()
            _note_created(created, "NewsPost", len(news_posts))
        else:
            logger.info("NewsPost уже есть — пропускаю")

        # --- ScheduleEvent ---
        if not await _exists(session, ScheduleEvent):
            schedule_events = [
                ScheduleEvent(
                    title="Старт этапа 1",
                    description="Старт первого этапа гонки «Авача 2027».",
                    kind=ScheduleKind.RACE.value,
                    stage_id=stages[0].id,
                    starts_at=datetime(2027, 3, 1, 2, 0, tzinfo=UTC),
                    ends_at=datetime(2027, 3, 1, 2, 30, tzinfo=UTC),
                    location="Петропавловск-Камчатский",
                    is_public=True,
                ),
                ScheduleEvent(
                    title="Открытие фестиваля «Берингия»",
                    description="Церемония открытия зимнего фестиваля, выступление творческих коллективов.",
                    kind=ScheduleKind.CULTURAL.value,
                    stage_id=None,
                    starts_at=datetime(2027, 3, 1, 6, 0, tzinfo=UTC),
                    ends_at=datetime(2027, 3, 1, 8, 0, tzinfo=UTC),
                    location="Центральная площадь",
                    is_public=True,
                ),
                ScheduleEvent(
                    title="Старт этапа 2",
                    description="Второй этап гонки через перевалы Налычево.",
                    kind=ScheduleKind.RACE.value,
                    stage_id=stages[1].id,
                    starts_at=datetime(2027, 3, 2, 2, 0, tzinfo=UTC),
                    ends_at=datetime(2027, 3, 2, 2, 30, tzinfo=UTC),
                    location="Налычево",
                    is_public=True,
                ),
                ScheduleEvent(
                    title="Концерт этнической музыки",
                    description="Вечерний концерт коллективов Камчатского края.",
                    kind=ScheduleKind.CULTURAL.value,
                    stage_id=None,
                    starts_at=datetime(2027, 3, 2, 9, 0, tzinfo=UTC),
                    ends_at=datetime(2027, 3, 2, 11, 0, tzinfo=UTC),
                    location="ДК «Берингия»",
                    is_public=True,
                ),
                ScheduleEvent(
                    title="Финиш этапа 3 и награждение",
                    description="Церемония финиша гонки и награждения победителей.",
                    kind=ScheduleKind.RACE.value,
                    stage_id=stages[2].id,
                    starts_at=datetime(2027, 3, 3, 4, 0, tzinfo=UTC),
                    ends_at=datetime(2027, 3, 3, 6, 0, tzinfo=UTC),
                    location="Финишный городок",
                    is_public=True,
                ),
                ScheduleEvent(
                    title="Ярмарка мастеров Камчатки",
                    description="Сувениры, ремёсла и традиционная кухня коренных народов.",
                    kind=ScheduleKind.OTHER.value,
                    stage_id=None,
                    starts_at=datetime(2027, 3, 3, 7, 0, tzinfo=UTC),
                    ends_at=datetime(2027, 3, 3, 12, 0, tzinfo=UTC),
                    location="Набережная",
                    is_public=True,
                ),
            ]
            session.add_all(schedule_events)
            await session.flush()
            _note_created(created, "ScheduleEvent", len(schedule_events))
        else:
            logger.info("ScheduleEvent уже есть — пропускаю")

        # --- FAQItem ---
        if not await _exists(session, FAQItem):
            faq_items = [
                FAQItem(
                    question=question,
                    answer=answer,
                    category=category,
                    order_index=i,
                    is_public=True,
                )
                for i, (question, answer, category) in enumerate(FAQ_ITEMS)
            ]
            session.add_all(faq_items)
            await session.flush()
            _note_created(created, "FAQItem", len(faq_items))
        else:
            logger.info("FAQItem уже есть — пропускаю")

        # --- ViewerLocation ---
        if not await _exists(session, ViewerLocation):
            viewer_locations = []
            for i, (name, kind, directions, travel_time, safety) in enumerate(VIEWER_LOCATIONS):
                lat, lon = _random_position(rng)
                viewer_locations.append(
                    ViewerLocation(
                        name=name,
                        description=f"Зрительская площадка: {name.lower()}.",
                        kind=kind.value,
                        lat=lat,
                        lon=lon,
                        address="Камчатский край",
                        directions=directions,
                        travel_time_minutes=travel_time,
                        parking_info="Бесплатная парковка у площадки.",
                        facilities=["Парковка", "Пункт обогрева", "Кафе"],
                        photo_url=None,
                        first_arrival_planned_at=now + timedelta(days=1, hours=i),
                        stage_id=first_stage.id if i < 2 else None,
                        safety_notes=safety,
                        is_public=True,
                    )
                )
            session.add_all(viewer_locations)
            await session.flush()
            _note_created(created, "ViewerLocation", len(viewer_locations))
        else:
            logger.info("ViewerLocation уже есть — пропускаю")

        # 4. Единственный commit в конце операции.
        await session.commit()

        # 5. Вывод сводки.
        print("\nСоздано:")
        for key in [
            "Season",
            "Discipline",
            "User",
            "Participant",
            "Stage",
            "Checkpoint",
            "Device",
            "TrackPoint",
            "StageRoutePoint",
            "OfficialMark",
            "FanSubscription",
            "PushSubscription",
            "NotificationQueue",
            "NewsPost",
            "ScheduleEvent",
            "FAQItem",
            "ViewerLocation",
        ]:
            print(f"  {key}: {created.get(key, 0)}")

        print("\nАдмин: admin / admin123")
        print("Открой /docs → GET /api/v1/participants")

        if users:
            first_user = users[0]
            token, _ = create_user_token(first_user.id, first_user.vk_user_id)
            print(f"\nТестовый JWT (пользователь 1):\n  {token}")
        else:
            print("\nПользователей нет — JWT не сгенерирован.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed dev database")
    parser.add_argument("--reset", action="store_true", help="Очистить перед seed")
    parser.add_argument("--users", type=int, default=30, help="Количество пользователей")
    parser.add_argument("--no-track", action="store_true", help="Без треков")
    parser.add_argument("--force", action="store_true", help="Разрешить в prod")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(
        main(
            reset=args.reset,
            users_count=args.users,
            no_track=args.no_track,
            force=args.force,
        )
    )
