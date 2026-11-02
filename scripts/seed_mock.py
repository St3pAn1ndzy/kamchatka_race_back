"""Скрипт для заполнения dev-БД тестовыми данными.

Запуск:
    poetry run python -m scripts.seed_mock
    poetry run python -m scripts.seed_mock --reset
    poetry run python -m scripts.seed_mock --users 50 --no-track
"""

import argparse
import asyncio
import hashlib
import json
import logging
import random
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

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
    RaceStatus,
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
from app.db.models.guest_item import GuestItem
from app.db.models.static_page import StaticPage
from app.enums import (
    CheckpointKind,
    NewsSource,
    NotificationEventType,
    NotificationStatus,
    ParticipantStatus,
    PublicationStatus,
    RaceState,
    ScheduleKind,
    StageStatus,
    ViewerLocationCategory,
    ViewerLocationGlyph,
    ViewerLocationKind,
)
from app.security.passwords import hash_password
from app.security.tokens import create_user_token
from app.services.cache import cache
from scripts.demo import SCENARIOS, scenario_environment

logger = logging.getLogger("avacha.seed")
settings = get_settings()

# --- Пути для медиа -------------------------------------------------------

SEED_MEDIA_DIR = Path("seed_media")
MEDIA_DIR = Path("media")
ROUTE_JSON_PATH = Path("data/route-kamchatka.json")


def _copy_seed_media(folder: str, filename: str, target_folder: str) -> str | None:
    """Копирует файл из seed_media/{folder}/ в media/{target_folder}/."""
    src = SEED_MEDIA_DIR / folder / filename
    if not src.exists():
        logger.warning(f"Нет файла seed_media/{folder}/{filename} — пропускаю")
        return None
    dst_dir = MEDIA_DIR / target_folder
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / filename
    shutil.copy2(src, dst)
    return f"/media/{target_folder}/{filename}"


# --- Константы seed-данных -------------------------------------------------

SEASON_YEAR = 2027
SEASON_TITLE = "Авача 2027"

DISCIPLINES = [
    ("long", "Длинная"),
    ("middle", "Средняя"),
    ("sprint", "Спринт"),
]

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

# Обновленные данные под 6 этапов Камчатки
STAGES_DATA = [
    {
        "number": 1,
        "name": "б/к им. Фатьянова — Пиначево",
        "distance": 34,
        "start_utc": "2027-02-07T02:00:00Z",
        "duration": 3,
    },
    {
        "number": 2,
        "name": "Пиначево — Налычево",
        "distance": 56,
        "start_utc": "2027-02-07T22:00:00Z",
        "duration": 8,
    },
    {
        "number": 3,
        "name": "Налычево — кольцевой",
        "distance": 71,
        "start_utc": "2027-02-08T22:00:00Z",
        "duration": 8,
    },
    {
        "number": 4,
        "name": "Налычево — ночной",
        "distance": 38,
        "start_utc": "2027-02-10T11:00:00Z",
        "duration": 6,
    },
    {
        "number": 5,
        "name": "Налычево — Пиначево",
        "distance": 56,
        "start_utc": "2027-02-11T22:00:00Z",
        "duration": 8,
    },
    {
        "number": 6,
        "name": "Пиначево — б/к им. Фатьянова",
        "distance": 34,
        "start_utc": "2027-02-13T00:00:00Z",
        "duration": 5,
    },
]

BASE_LAT = 53.30
BASE_LON = 158.50
LAT_SPREAD = 0.25
LON_SPREAD = 0.25

NEWS_TITLES = [
    "Старт «Авачи 2027» — всё готово к началу гонки",
    "Первый этап завершён: результаты и время лидеров",
    "Победитель первого дня — неожиданный рывок",
    "Этап 2: преодоление перевалов Налычево",
    "Финиш гонки позади: итоги «Авачи 2027»",
]

FAQ_ITEMS = [
    (
        "Как добраться до места старта гонки?",
        "До старта в Петропавловске-Камчатском ходят городские автобусы и такси. Для зрителей на финише этапа организуют трансфер от гостиниц — расписание публикуется в программе.",
        "Транспорт",
    ),
    (
        "Есть ли парковка у места старта?",
        "Да, рядом со стартовой площадкой оборудована бесплатная парковка на 150 мест. В дни этапов парковка открывается с 07:00.",
        "Транспорт",
    ),
    (
        "Что взять с собой на трассу?",
        "Тёплую одежду, термос с горячим чаем и защиту от ветра. На КП работают пункты обогрева.",
        "Безопасность",
    ),
    (
        "Что делать при экстренной ситуации на трассе?",
        "На каждом контрольном пункте дежурит судья и медицинский работник. Зрителям нельзя выходить на трассу во время прохождения упряжек.",
        "Безопасность",
    ),
    (
        "Где остановиться в Петропавловске-Камчатском?",
        "В городе работают гостиницы разного уровня, а также хостелы и гостевые дома. Рекомендуем бронировать заранее — в дни фестиваля спрос высокий.",
        "Проживание",
    ),
]

GETTING_HERE_FAQ = [
    (
        "Где находится Камчатка",
        "Камчатка — полуостров на северо-востоке России. Омывается Тихим океаном, Охотским и Беринговым морями.",
    ),
    (
        "Как добраться до полуострова",
        "Самолёт — самый быстрый способ. Прямые рейсы из Москвы (~9 часов) и из Владивостока.",
    ),
    (
        "Как купить самые дешёвые билеты",
        "Билеты дешевле при покупке за 2-3 месяца. Следите за акциями авиакомпаний.",
    ),
    (
        "Каким транспортом можно воспользоваться",
        "Внутри региона — автобусы, такси, аренда авто. До некоторых локаций — только вертолёт.",
    ),
    (
        "Где можно остановиться",
        "Гостиницы, хостелы, гостевые дома. Бронируйте заранее — в дни фестиваля спрос высокий.",
    ),
]

SAFETY_FAQ = [
    (
        "Погода и метели",
        "Камчатская погода крайне переменчива. Метели и сильный ветер могут начаться внезапно. Обязательно следите за прогнозом и не выходите на маршруты в плохую видимость.",
    ),
    (
        "Лавины",
        "В горной местности всегда есть риск схода лавин. Не выходите за пределы оборудованных трасс и слушайте рекомендации спасателей.",
    ),
    (
        "Сейсмичность",
        "Камчатка — сейсмоактивный регион. При землетрясении не паникуйте, не пользуйтесь лифтами и держитесь подальше от окон и тяжелых предметов.",
    ),
    (
        "Изоляция и рельеф",
        "Многие локации находятся вдали от цивилизации, сотовая связь может отсутствовать. Всегда сообщайте о своих планах и имейте при себе запас еды и воды.",
    ),
    (
        "Риски вне зависимости от сезона",
        "Дикая природа требует уважения. Не приближайтесь к диким животным, не оставляйте мусор и строго соблюдайте правила безопасности на вулканах.",
    ),
]

CONTACT_BLOCKS = [
    {
        "icon": "email",
        "title": "Написать на почту",
        "subtitle": "info@sleddog-russia.ru",
        "url": "mailto:info@sleddog-russia.ru",
    },
    {
        "icon": "vk",
        "title": "Сообщения сообщества",
        "subtitle": "Ответим во ВКонтакте",
        "url": "https://vk.me/avacha.race",
    },
    {
        "icon": "site",
        "title": "sleddog-russia.ru",
        "subtitle": "Официальный сайт",
        "url": "https://sleddog-russia.ru/",
    },
    {
        "icon": "vk",
        "title": "vk.ru/avacha.race",
        "subtitle": "Сообщество",
        "url": "https://vk.com/avacha.race",
    },
    {
        "icon": "telegram",
        "title": "@avacha.race",
        "subtitle": "Telegram",
        "url": "https://t.me/avacha_race",
    },
]

VIEWER_LOCATIONS = [
    # ═══ Сцены (category=stages) ═══
    {
        "name": "Главная сцена",
        "kind": ViewerLocationKind.FESTIVAL,
        "category": ViewerLocationCategory.STAGES,
        "glyph": ViewerLocationGlyph.MIC,
        "description": "Концерты и главные события фестиваля",
        "lat": 53.0960,
        "lon": 158.6370,
    },
    # ═══ Площадки (category=areas) ═══
    {
        "name": "Фотозона",
        "kind": ViewerLocationKind.FESTIVAL,
        "category": ViewerLocationCategory.AREAS,
        "glyph": ViewerLocationGlyph.IMAGE,
        "description": "Оформленная площадка для фото",
        "lat": 53.0954,
        "lon": 158.6362,
    },
    {
        "name": "Этнозона",
        "kind": ViewerLocationKind.FESTIVAL,
        "category": ViewerLocationCategory.AREAS,
        "glyph": ViewerLocationGlyph.GLOBE,
        "description": "Традиционные ремёсла и выставки",
        "lat": 53.0959,
        "lon": 158.6356,
    },
    # ═══ Еда (category=food) ═══
    {
        "name": "Фудкорт",
        "kind": ViewerLocationKind.FESTIVAL,
        "category": ViewerLocationCategory.FOOD,
        "glyph": ViewerLocationGlyph.FOOD,
        "description": "Горячее питание и напитки",
        "lat": 53.0968,
        "lon": 158.6364,
    },
    # ═══ Детям (category=kids) ═══
    {
        "name": "Детская зона",
        "kind": ViewerLocationKind.FESTIVAL,
        "category": ViewerLocationCategory.KIDS,
        "glyph": ViewerLocationGlyph.SMILE,
        "description": "Анимация и игры для детей",
        "lat": 53.0949,
        "lon": 158.6378,
    },
]

ABOUT_PAGE_CONTENT = """\
«Авача»

Физкультурно-туристическое мероприятие по ездовому спорту «Авача» — всероссийская гонка, проходящая на Камчатке в рамках зимнего фестиваля при поддержке Правительства Камчатского края и Федерации развития ездового спорта, объединяющая спорт, туризм, культуру и традиции региона.

Гонка «Авача» является самой сложной гонкой в России и одной из самых сложных в мире. Единственная горная гонка, маршрут которой проходит по подножиям действующих вулканов. Участие принимают только опытные сильнейшие спортсмены страны по ездовому спорту, выступающие в дисциплине на длинные дистанции.

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 16px 0;">
  <img src="/media/pages/about1.jpg" style="width: 100%; border-radius: 8px; object-fit: cover; aspect-ratio: 4/3;">
  <img src="/media/pages/about2.jpg" style="width: 100%; border-radius: 8px; object-fit: cover; aspect-ratio: 4/3;">
</div>

Маршрут пролегает через живописные горные перевалы и территорию природного парка «Налычево», приобщая к гонкам выносливости и грамотной тактики. Гонка длится 6 дней, включая ночной этап. Общая протяженность примерно 300 км, суммарный набор высоты — более 4000 метров. Трасса включает в себя: заснеженные перевалы и спуски и снегопады в ночное время, что предъявляет повышенные требования к снаряжению и подготовке собак. Ежегодно интерес к гонке растет как каюров Камчатского края, так и каюров из других субъектов Российской Федерации. Кроме того, желание участвовать изъявили представители иностранных государств — это Эстония, Чехия, Италия, Финляндия и Германия.

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 16px 0;">
  <img src="/media/pages/about3.jpg" style="width: 100%; border-radius: 8px; object-fit: cover; aspect-ratio: 4/3;">
  <img src="/media/pages/about4.jpg" style="width: 100%; border-radius: 8px; object-fit: cover; aspect-ratio: 4/3;">
</div>

Участие в гонке «Авача» — это возможность испытать себя в суровых условиях, проверить себя и своих собак, преодолевая длинную дистанцию около 300 км по заснеженным вершинам парков вулканов, познакомиться с дикой природой Камчатки и единомышленниками из разных уголков страны.
"""

# --- Утилиты ---------------------------------------------------------------


def _random_position(rng: random.Random) -> tuple[float, float]:
    lat = round(BASE_LAT + rng.uniform(-LAT_SPREAD, LAT_SPREAD), 6)
    lon = round(BASE_LON + rng.uniform(-LON_SPREAD, LON_SPREAD), 6)
    return lat, lon


def _dedup_key(imei: str, recorded_at: datetime) -> str:
    raw = f"{imei}:{recorded_at.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _exists(session, model) -> bool:
    result = await session.execute(select(model.id).limit(1))
    return result.scalar_one_or_none() is not None


async def _exists_by_slug(session, model, slug: str) -> bool:
    result = await session.execute(select(model.id).where(model.slug == slug).limit(1))
    return result.scalar_one_or_none() is not None


def _note_created(created: dict[str, int], key: str, amount: int) -> None:
    created[key] = created.get(key, 0) + amount


async def ensure_stages(
    session: AsyncSession, season: Season, stage_data: list[dict], no_track: bool = False
) -> list[Stage]:
    """Добавляет недостающие номера только в выбранный сезон без изменения существующих"""
    data_numbers = set()
    for data in stage_data:
        number = data["number"]
        if type(number) is not int or number <= 0 or number in data_numbers:
            raise ValueError(f"Недопустимый или повторяющийся номер этапа seed: {number}")
        data_numbers.add(number)

    with session.no_autoflush:
        locked_id = await session.scalar(
            select(Season.id).where(Season.id == season.id).with_for_update()
        )
        if locked_id is None:
            raise ValueError(f"Сезон {season.id} не найден")
        stages = list(
            await session.scalars(
                select(Stage).where(Stage.season_id == season.id).order_by(Stage.number, Stage.id)
            )
        )
        existing_numbers = set()
        for stage in stages:
            if stage.number <= 0 or stage.number in existing_numbers:
                raise ValueError(
                    f"Недопустимый или повторяющийся номер этапа {stage.number} "
                    f"в сезоне {season.id}"
                )
            existing_numbers.add(stage.number)

        added = []
        for data in stage_data:
            if data["number"] in existing_numbers:
                continue
            start_dt = datetime.fromisoformat(data["start_utc"].replace("Z", "+00:00"))
            active = data["number"] == 1 and not no_track
            added.append(
                Stage(
                    name=f"Этап {data['number']}. {data['name']}",
                    distance_km=float(data["distance"]),
                    start_time=start_dt,
                    finish_time=start_dt + timedelta(hours=data["duration"]),
                    order_index=data["number"] - 1,
                    tracker_interval_seconds=1200,
                    status=StageStatus.ACTIVE.value if active else StageStatus.PLANNED.value,
                    results_publication=(
                        PublicationStatus.PROVISIONAL.value
                        if active
                        else PublicationStatus.DRAFT.value
                    ),
                    season_id=season.id,
                    number=data["number"],
                )
            )
        if added:
            session.add_all(added)
            await session.flush(added)
        logger.info("Stage: добавлено %s, сохранено %s", len(added), len(stages))
        return sorted([*stages, *added], key=lambda stage: stage.number)


# --- Основная логика -------------------------------------------------------


async def validate_seed_scenario(
    session: AsyncSession, scenario: str, stage_data: list[dict]
) -> None:
    """Отклоняет смешивание явного профиля с несовместимыми данными до первой записи"""
    with session.no_autoflush:
        season_id = await session.scalar(
            select(Season.id).where(Season.year == SEASON_YEAR).with_for_update()
        )
        stages = (
            list(
                await session.scalars(
                    select(Stage)
                    .where(Stage.season_id == season_id)
                    .order_by(Stage.number, Stage.id)
                )
            )
            if season_id is not None
            else []
        )
        numbers = [stage.number for stage in stages]
        expected = {data["number"] for data in stage_data}
        incompatible = bool(stages) and (
            len(numbers) != len(set(numbers)) or set(numbers) != expected
        )
        if scenario == "route-import":
            incompatible = incompatible or any(
                stage.status != StageStatus.PLANNED.value
                or stage.results_publication != PublicationStatus.DRAFT.value
                for stage in stages
            )
            has_gps = await _exists(session, TrackPoint)
            has_marks = await _exists(session, OfficialMark)
            has_sos = await session.scalar(select(Device.id).where(Device.sos_active).limit(1))
            race = await session.scalar(select(RaceStatus).limit(1))
            incompatible = (
                incompatible
                or has_gps
                or has_marks
                or has_sos is not None
                or (race is not None and race.status != RaceState.UPCOMING.value)
            )
        if incompatible:
            raise ValueError(f"Данные несовместимы со сценарием {scenario}, пересоздайте с --reset")


async def main(
    *, reset: bool, users_count: int, no_track: bool, force: bool, scenario: str = "standard"
) -> None:
    """Заполняет стандартную базу или один из явных демонстрационных профилей"""
    if scenario not in {"standard", "overview", "route-import"}:
        raise ValueError(f"Неизвестный сценарий seed: {scenario}")
    if scenario != "standard":
        scenario_environment(scenario, settings)
        if SCENARIOS[scenario].database != settings.POSTGRES_DB:
            raise ValueError(
                f"Сценарий {scenario} требует демонстрационную базу {SCENARIOS[scenario].database}"
            )
        if SCENARIOS[scenario].redis_db != settings.REDIS_DB:
            raise ValueError(f"Сценарий {scenario} требует Redis DB={SCENARIOS[scenario].redis_db}")
    stage_data = STAGES_DATA[:3] if scenario == "overview" else STAGES_DATA
    if scenario == "route-import":
        no_track = True
    elif scenario == "overview":
        no_track = False
    if settings.ENV != "dev" and not force:
        raise RuntimeError(
            f"Seed разрешён только в ENV=dev, сейчас ENV={settings.ENV!r}. Для прод-окружения используйте --force."
        )

    if no_track:
        logger.info("--no-track: треки, маршрут и судейские отметки будут пропущены")

    rng = random.Random(2027)
    created: dict[str, int] = {}

    async with async_session_factory() as session:
        if scenario != "standard" and not reset:
            await validate_seed_scenario(session, scenario, stage_data)
        if reset:
            logger.info("Сброс: очищаю таблицы")
            reset_order = [
                AuditLog,
                OfficialMark,
                TrackPoint,
                StageRoutePoint,
                Device,
                Checkpoint,
                Stage,
                Discipline,
                Season,
                FanSubscription,
                SavedItem,
                ShareEvent,
                NotificationQueue,
                PushSubscription,
                UserFeedback,
                Participant,
                NewsPost,
                ScheduleEvent,
                FAQItem,
                ViewerLocation,
                StaticPage,
                GuestItem,
                AdminAccount,
                User,
            ]
            tables = ", ".join(m.__tablename__ for m in reset_order)
            await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

        now = datetime.now(tz=UTC)

        # --- Season ---
        season = await session.scalar(select(Season).where(Season.year == SEASON_YEAR))
        if season is None:
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
            logger.info("Season уже есть — пропускаю")

        # --- Discipline ---
        if not await _exists(session, Discipline):
            disciplines = [
                Discipline(
                    season_id=season.id, code=code, name=name, sort_order=order, is_active=True
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
            users = [
                User(
                    vk_user_id=100000 + i,
                    first_name=f"Болельщик {i}",
                    last_name="",
                    platform="vk",
                    notifications_allowed=(i % 2 == 0),
                    consent_version="1.0",
                    consent_accepted_at=now - timedelta(days=30),
                    onboarding_passed_at=now - timedelta(days=20),
                )
                for i in range(1, users_count + 1)
            ]
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
            statuses = (
                [ParticipantStatus.ACTIVE.value] * 10
                + [ParticipantStatus.FINISHED.value] * 3
                + [ParticipantStatus.WITHDRAWN.value] * 1
                + [ParticipantStatus.REGISTERED.value] * 1
            )
            participants = []
            for index, (name, region) in enumerate(MUSHERS):
                photo_url = _copy_seed_media("participants", f"{index + 1}.jpg", "participants")
                participants.append(
                    Participant(
                        name=name,
                        number=index + 1,
                        region=region,
                        discipline_id=discipline_ids[index % len(discipline_ids)],
                        photo_url=photo_url,
                        bio=f"Опытный каюр из региона {region}. Участник гонки «{SEASON_TITLE}».",
                        dogs_count=rng.randint(4, 12),
                        status=statuses[index],
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
        existing_stage_ids = set(
            await session.scalars(select(Stage.id).where(Stage.season_id == season.id))
        )
        stages = await ensure_stages(session, season, stage_data, no_track=no_track)
        new_stages = [stage for stage in stages if stage.id not in existing_stage_ids]
        _note_created(created, "Stage", len(new_stages))

        first_stage = stages[0]
        first_admin = admin

        # --- Загрузка реального маршрута из JSON ---
        route_json = {}
        if scenario != "route-import":
            if not ROUTE_JSON_PATH.exists():
                raise RuntimeError(
                    f"Файл {ROUTE_JSON_PATH} не найден. "
                    f"Сид не может продолжить без реальной геометрии маршрута. "
                    f"Проверь, что в docker-compose.yaml у сервиса api смонтирован ./data:/app/data"
                )

            with open(ROUTE_JSON_PATH, encoding="utf-8") as f:
                route_json = json.load(f)

            # Проверяем геометрию только этапов выбранного сценария
            missing_stages = [
                data["number"]
                for data in stage_data
                if not any(
                    js["number"] == data["number"] and js.get("coordinates")
                    for js in route_json.get("stages", [])
                )
            ]
            if missing_stages:
                raise RuntimeError(
                    f"В {ROUTE_JSON_PATH} нет координат для этапов: {missing_stages}. "
                    f"Проверь файл — все {len(stage_data)} этапов должны иметь массив coordinates."
                )

        # --- Checkpoint & StageRoutePoint ---
        checkpoints = []
        if scenario != "route-import" and new_stages:
            for stage in new_stages:
                json_stage = next(
                    (js for js in route_json.get("stages", []) if js["number"] == stage.number),
                    None,
                )

                if json_stage and json_stage.get("coordinates"):
                    coords = json_stage["coordinates"]
                else:
                    # Фоллбэк: прямая линия
                    start_lat, start_lon = _random_position(rng)
                    finish_lat, finish_lon = _random_position(rng)
                    coords = []
                    for i in range(20):
                        ratio = i / 19
                        lat = start_lat + (finish_lat - start_lat) * ratio
                        lon = start_lon + (finish_lon - start_lon) * ratio
                        coords.append([lon, lat])

                # 1. Route Points
                if not no_track:
                    route_points = [
                        StageRoutePoint(stage_id=stage.id, position=i, lat=lat, lon=lon)
                        for i, (lon, lat) in enumerate(coords)
                    ]
                    session.add_all(route_points)
                    _note_created(created, "StageRoutePoint", len(route_points))

                # 2. Checkpoints
                def make_cp(stage_obj, code, name, kind, coord, order_idx):
                    return Checkpoint(
                        stage_id=stage_obj.id,
                        code=code,
                        name=name,
                        kind=kind,
                        description=f"{name} (этап {stage_obj.number})",
                        lat=coord[1],
                        lon=coord[0],
                        altitude=100,
                        km_from_race_start=0,
                        order_index=order_idx,
                        has_judge=True,
                        is_public=True,
                    )

                cp_start = make_cp(
                    stage, "Старт", "Старт этапа", CheckpointKind.START.value, coords[0], 0
                )
                cp_1 = make_cp(
                    stage,
                    "КП-1",
                    "Контрольный пункт 1",
                    CheckpointKind.CHECKPOINT.value,
                    coords[int(len(coords) * 0.3)],
                    1,
                )
                cp_2 = make_cp(
                    stage,
                    "КП-2",
                    "Контрольный пункт 2",
                    CheckpointKind.CHECKPOINT.value,
                    coords[int(len(coords) * 0.7)],
                    2,
                )
                cp_finish = make_cp(
                    stage, "Финиш", "Финиш этапа", CheckpointKind.FINISH.value, coords[-1], 3
                )
                checkpoints.extend([cp_start, cp_1, cp_2, cp_finish])

            session.add_all(checkpoints)
            await session.flush()
            _note_created(created, "Checkpoint", len(checkpoints))
        checkpoints = (
            (await session.execute(select(Checkpoint).order_by(Checkpoint.id))).scalars().all()
        )

        if not no_track:
            first_stage_cps = sorted(
                [cp for cp in checkpoints if cp.stage_id == first_stage.id],
                key=lambda c: c.order_index,
            )
            path_start = next(cp for cp in first_stage_cps if cp.kind == CheckpointKind.START.value)
            path_finish = next(
                cp for cp in first_stage_cps if cp.kind == CheckpointKind.FINISH.value
            )

        # --- RaceStatus (текущий режим гонки) ---
        if not await _exists(session, RaceStatus):
            session.add(
                RaceStatus(
                    status=(
                        RaceState.UPCOMING.value
                        if scenario == "route-import"
                        else RaceState.LIVE.value
                    ),
                    current_stage_id=None if scenario == "route-import" else first_stage.id,
                )
            )
            await session.flush()
            _note_created(created, "RaceStatus", 1)

        # --- Device ---
        if not await _exists(session, Device):
            devices = [
                Device(
                    iridium_number=f"{i:03d}",
                    imei=f"30023456{i:07d}",
                    name=f"Трекер №{i:03d}",
                    participant_id=participants[i - 1].id,
                    stage_id=first_stage.id,
                    is_active=True,
                    battery_percent=rng.randint(10, 100),
                    sos_active=(scenario != "route-import" and i in (3, 8)),
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

        # --- TrackPoint (на основе реального маршрута) ---
        track_points: list[TrackPoint] = []
        if not no_track and not await _exists(session, TrackPoint):
            points_count = 20
            track_total_km = first_stage.distance_km
            FRESHNESS_AGE_MINUTES = [5, 25, 120, 8, 30, 180, 3, 22, 60]

            # Достаем реальные точки маршрута
            route_pts = (
                (
                    await session.execute(
                        select(StageRoutePoint)
                        .where(StageRoutePoint.stage_id == first_stage.id)
                        .order_by(StageRoutePoint.position)
                    )
                )
                .scalars()
                .all()
            )

            for pi, participant in enumerate(participants):
                if pi >= len(devices):
                    break
                device = devices[pi]
                max_ratio = ((pi + 1) / (len(participants) + 1)) * 0.9
                last_age_min = FRESHNESS_AGE_MINUTES[pi % len(FRESHNESS_AGE_MINUTES)]

                for j in range(points_count):
                    ratio = (j / (points_count - 1)) * max_ratio

                    if route_pts:
                        route_idx = int(ratio * (len(route_pts) - 1))
                        pt = route_pts[route_idx]
                        lat, lon = pt.lat, pt.lon
                    else:
                        lat, lon = _random_position(rng)

                    minutes_ago = last_age_min + 20 * (points_count - 1 - j)
                    recorded_at = now - timedelta(minutes=minutes_ago)
                    avg_speed = None
                    if j > 0:
                        prev_ratio = ((j - 1) / (points_count - 1)) * max_ratio
                        km_delta = (ratio - prev_ratio) * track_total_km
                        avg_speed = round(km_delta / (20 / 60), 1)

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
                            average_speed_kmh=avg_speed,
                            km_from_start=round(ratio * track_total_km, 2),
                            recorded_at=recorded_at,
                            is_confirmed=True,
                        )
                    )

            session.add_all(track_points)
            await session.flush()
            _note_created(created, "TrackPoint", len(track_points))

            last_by_device = {}
            for tp in track_points:
                if (
                    tp.device_id not in last_by_device
                    or tp.recorded_at > last_by_device[tp.device_id]
                ):
                    last_by_device[tp.device_id] = tp.recorded_at
            for device in devices:
                if device.id in last_by_device:
                    device.last_message_at = last_by_device[device.id]
        elif not no_track:
            logger.info("TrackPoint уже есть — пропускаю")

        # --- OfficialMark ---
        if not no_track and not await _exists(session, OfficialMark):
            official_marks = []
            for participant in participants:
                participant_points = [
                    tp for tp in track_points if tp.participant_id == participant.id
                ]
                if not participant_points:
                    continue
                participant_points.sort(key=lambda tp: tp.recorded_at)
                official_marks.append(
                    OfficialMark(
                        participant_id=participant.id,
                        checkpoint_id=path_start.id,
                        mark_time=participant_points[0].recorded_at,
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
                        mark_time=participant_points[-1].recorded_at,
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

        # --- FanSubscription ---
        if not await _exists(session, FanSubscription):
            fan_subscriptions = []
            user_ids = [u.id for u in users]
            for participant in participants:
                for user_id in rng.sample(user_ids, min(rng.randint(5, 10), len(user_ids))):
                    fan_subscriptions.append(
                        FanSubscription(user_id=user_id, participant_id=participant.id)
                    )
            session.add_all(fan_subscriptions)
            await session.flush()
            _note_created(created, "FanSubscription", len(fan_subscriptions))

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

        # --- NotificationQueue ---
        if not await _exists(session, NotificationQueue):
            notifications = []
            event_types = list(NotificationEventType)
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

        # --- NewsPost ---
        if not await _exists(session, NewsPost):
            news_posts = []
            for i, title in enumerate(NEWS_TITLES):
                cover_url = _copy_seed_media("news", f"news{i + 1}.jpg", "news")
                news_posts.append(
                    NewsPost(
                        title=title,
                        lead=f"Кратко о событиях дня: {title.lower().rstrip('.')}.",
                        body=f"Подробный репортаж. {title}. Следите за обновлениями в официальном сообществе ВКонтакте.",
                        cover_url=cover_url,
                        source=NewsSource.MANUAL.value,
                        vk_url=None,
                        stage_id=first_stage.id if i < 2 else None,
                        published_at=now - timedelta(days=max(0, 2 - i // 2)),
                        is_published=(i % 3 != 0),
                        is_important=(i == 1),
                        is_pinned=(i == 0),
                    )
                )
            session.add_all(news_posts)
            await session.flush()
            _note_created(created, "NewsPost", len(news_posts))

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
                    title="Открытие фестиваля «Авача»",
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
                    location="ДК «Авача»",
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

        # --- FAQItem ---
        if not await _exists(session, FAQItem):
            faq_items = [
                FAQItem(question=q, answer=a, category=c, order_index=i, is_public=True)
                for i, (q, a, c) in enumerate(FAQ_ITEMS)
            ]
            faq_items.extend(
                [
                    FAQItem(
                        question=q, answer=a, category="getting_here", order_index=i, is_public=True
                    )
                    for i, (q, a) in enumerate(GETTING_HERE_FAQ)
                ]
            )
            faq_items.extend(
                [
                    FAQItem(question=q, answer=a, category="safety", order_index=i, is_public=True)
                    for i, (q, a) in enumerate(SAFETY_FAQ)
                ]
            )
            session.add_all(faq_items)
            await session.flush()
            _note_created(created, "FAQItem", len(faq_items))

        # --- ViewerLocation ---
        if not await _exists(session, ViewerLocation):
            viewer_locations = []
            for i, loc in enumerate(VIEWER_LOCATIONS):
                viewer_locations.append(
                    ViewerLocation(
                        name=loc["name"],
                        description=loc.get("description")
                        or f"Зрительская площадка: {loc['name'].lower()}.",
                        kind=loc["kind"],
                        category=loc["category"],
                        glyph=loc.get("glyph", ViewerLocationGlyph.PIN.value),
                        lat=loc["lat"],
                        lon=loc["lon"],
                        address=loc.get("address", "Камчатский край"),
                        directions=loc.get("directions"),
                        travel_time_minutes=loc.get("travel_time_minutes"),
                        parking_info=loc.get("parking_info", "Бесплатная парковка у площадки."),
                        facilities=loc.get("facilities", ["Парковка", "Пункт обогрева", "Кафе"]),
                        photo_url=loc.get("photo_url"),
                        first_arrival_planned_at=loc.get("first_arrival_planned_at")
                        or (now + timedelta(days=1, hours=i)),
                        stage_id=loc.get("stage_id", first_stage.id if i < 2 else None),
                        safety_notes=loc.get("safety_notes", ""),
                        is_public=loc.get("is_public", True),
                    )
                )
            session.add_all(viewer_locations)
            await session.flush()
            _note_created(created, "ViewerLocation", len(viewer_locations))

        # --- StaticPage ---
        pages_to_create = [
            ("about", "О гонке «Авача 2027»", "about_cover.jpg", ABOUT_PAGE_CONTENT.strip(), []),
            ("guests", "Гостям", "guests_cover.jpg", "Добро пожаловать на Камчатку!", []),
            ("guests-getting-here", "Как добраться", "getting_here_cover.jpg", "", []),
            ("guests-what-to-bring", "Что взять с собой", "what_to_bring_cover.jpg", "", []),
            ("guests-safety", "Безопасность зимой", "safety_cover.jpg", "", []),
            ("faq", "Ответы на частые вопросы", "faq_cover.jpg", "", []),
            ("contacts", "Контакты", "contacts_cover.jpg", "", CONTACT_BLOCKS),
        ]
        for slug, title, cover_file, content, blocks in pages_to_create:
            if await _exists_by_slug(session, StaticPage, slug):
                continue
            cover_url = _copy_seed_media("pages", cover_file, "pages") if cover_file else None
            session.add(
                StaticPage(
                    slug=slug,
                    title=title,
                    content=content,
                    cover_url=cover_url,
                    blocks=blocks,
                    is_published=True,
                )
            )
            _note_created(created, "StaticPage", 1)
        await session.flush()

        # --- GuestItem ---
        if not await _exists(session, GuestItem):
            guest_items = [
                GuestItem(
                    section="clothing",
                    title="Первый слой",
                    text="Качественное термобелье (синтетика или шерсть мериноса), которое отводит влагу.",
                    order_index=1,
                    image_url=_copy_seed_media("guests", "clothing1.jpg", "guests"),
                ),
                GuestItem(
                    section="clothing",
                    title="Второй слой",
                    text="Плотная флисовая кофта или свитер из шерсти.",
                    order_index=2,
                ),
                GuestItem(
                    section="clothing",
                    title="Верхний слой",
                    text="Тёплая пуховая куртка (пух-перо) с глубоким капюшоном и непродуваемые утеплённые штаны.",
                    order_index=3,
                ),
                GuestItem(
                    section="clothing",
                    title="Головной убор и аксессуары",
                    text="Тёплая шапка, закрывающая уши, флисовый шарф и тёплые варежки.",
                    order_index=4,
                ),
                GuestItem(
                    section="clothing",
                    title="Для отдыха",
                    text="Купальник и лёгкие тапочки — зимой на Камчатке популярны купания в термальных источниках.",
                    order_index=5,
                ),
                GuestItem(
                    section="shoes",
                    title="Для города и полноценных прогулок",
                    text="Кожаные утеплённые ботинки или высокие сапоги с толстой нескользящей подошвой (из термопластичной резины или с глубоким протектором). Утеплитель: натуральный мех или плотная шерсть. Обувь должна быть высокой — выше щиколотки.",
                    order_index=1,
                    image_url=_copy_seed_media("guests", "shoes1.jpg", "guests"),
                ),
                GuestItem(
                    section="shoes",
                    title="Для активного отдыха, экскурсий",
                    text="Специальные зимние / экспедиционные ботинки с хорошим температурным запасом. Сапоги из ЭВА с тёплым многослойным вкладышем — незаменимы в сильный мороз, когда вы долго стоите на улице, или при поездках на снегоходах. Высокие треккинговые ботинки с мембраной (Gore-Tex) и качественным утеплителем (на тинсулейте), если планируются активные прогулки по утоптанному снегу.",
                    order_index=2,
                ),
                GuestItem(
                    section="shoes",
                    title="Дополнительная обувь",
                    text="Легкие кроссовки или ботинки для помещений / отеля. Сланцы / шлепанцы — пригодятся, если вы собираетесь в термальные источники.",
                    order_index=3,
                ),
                GuestItem(
                    section="equipment",
                    title="Мощный Powerbank",
                    text="На холоде аккумуляторы разряжаются очень быстро. Держите пауэрбанк во внутреннем кармане ближе к телу.",
                    order_index=1,
                    image_url=_copy_seed_media("guests", "equipment1.jpg", "guests"),
                ),
                GuestItem(
                    section="equipment",
                    title="Термос",
                    text="Горячий чай или морс на маршруте, во время катания на снегоходах или поездки к вулканам.",
                    order_index=2,
                ),
                GuestItem(
                    section="equipment",
                    title="Солнцезащитные очки",
                    text="Зимой солнце от снега светит очень ярко, ультрафиолет сильный.",
                    order_index=3,
                ),
                GuestItem(
                    section="equipment",
                    title="Гигиеническая помада и жирный защитный крем",
                    text="От мороза и ветра губы и лицо обветриваются мгновенно.",
                    order_index=4,
                ),
                GuestItem(
                    section="equipment",
                    title="Аптечка",
                    text="Базовый набор лекарств + таблетки от укачивания.",
                    order_index=5,
                ),
            ]
            session.add_all(guest_items)
            await session.flush()
            _note_created(created, "GuestItem", len(guest_items))

        # --- Один commit в конце ---
        await session.commit()

        # ═══ СБРОС КЭША ═══
        await cache.invalidate_pattern("public:*")
        await cache.invalidate_pattern("admin:*")
        logger.info("Кэш public:* и admin:* сброшен")

        # --- Сводка ---
        print("\nСоздано:")
        for key in [
            "Season",
            "Discipline",
            "User",
            "Participant",
            "Stage",
            "Checkpoint",
            "RaceStatus",
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
            "StaticPage",
            "GuestItem",
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
    parser.add_argument(
        "--scenario",
        choices=("standard", "overview", "route-import"),
        default="standard",
        help="Стандартные 6 этапов, обзор 3 этапов или подготовка 6 этапов к импорту",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(
        main(
            reset=args.reset,
            users_count=args.users,
            no_track=args.no_track,
            force=args.force,
            scenario=args.scenario,
        )
    )
