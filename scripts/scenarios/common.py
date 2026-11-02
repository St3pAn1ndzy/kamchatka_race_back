"""Общие helpers для сценариев. Вызывается из seed_mock.py один раз."""

import json
import random
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AdminAccount,
    Checkpoint,
    Discipline,
    FAQItem,
    GuestItem,
    NewsPost,
    Participant,
    ScheduleEvent,
    Season,
    Stage,
    StageRoutePoint,
    StaticPage,
    User,
    ViewerLocation,
)
from app.enums import (
    CheckpointKind,
    NewsSource,
    ParticipantStatus,
    PublicationStatus,
    ScheduleKind,
    StageStatus,
    ViewerLocationGlyph,
)
from app.security.passwords import hash_password
from scripts.seed_mock_data import (
    ABOUT_PAGE_CONTENT,
    CONTACT_BLOCKS,
    DISCIPLINES,
    FAQ_ITEMS,
    GETTING_HERE_FAQ,
    MUSHERS,
    NEWS_TITLES,
    SAFETY_FAQ,
    STAGES_DATA,
    VIEWER_LOCATIONS,
)

ROUTE_JSON_PATH = Path("data/route-kamchatka.json")
SEED_MEDIA_DIR = Path("seed_media")


def _copy_media(folder: str, filename: str, target: str) -> str | None:
    src = SEED_MEDIA_DIR / folder / filename
    if not src.exists():
        return None
    dst = Path("media") / target / filename
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return f"/media/{target}/{filename}"


async def seed_base(session: AsyncSession, created: dict[str, int]) -> dict:
    """Season, disciplines, admin, users, route, checkpoints, program, content.

    Возвращает:
        dict с season, stages, checkpoints, users, admin, participants
        (участники создаются здесь, но их статус — за сценарием).
    """
    now = datetime.now(tz=UTC)

    # ── Season ──
    season = Season(
        year=2027,
        title="Авача 2027",
        starts_at=datetime(2027, 2, 27, tzinfo=UTC),
        ends_at=datetime(2027, 3, 6, tzinfo=UTC),
        is_active=True,
    )
    session.add(season)
    await session.flush()
    created["Season"] = 1

    # ── Disciplines ──
    disciplines = [
        Discipline(season_id=season.id, code=code, name=name, sort_order=i, is_active=True)
        for i, (code, name) in enumerate(DISCIPLINES)
    ]
    session.add_all(disciplines)
    await session.flush()
    discipline_ids = [d.id for d in disciplines]
    created["Discipline"] = len(disciplines)

    # ── Admin ──
    admin = AdminAccount(
        login="admin",
        password_hash=hash_password("admin123"),
        display_name="Главный администратор",
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    created["AdminAccount"] = 1

    # ── Users ──
    users = [
        User(
            vk_user_id=100000 + i,
            first_name=f"Болельщик {i}",
            last_name="",
            platform="vk",
            notifications_allowed=(i % 2 == 0),
            consent_version="1.0",
            consent_accepted_at=now - timedelta(days=30),
        )
        for i in range(1, 31)
    ]
    session.add_all(users)
    await session.flush()
    created["User"] = len(users)

    # ── Participants (все registered, статус меняет сценарий) ──
    participants = []
    for index, (name, region) in enumerate(MUSHERS):
        photo_url = _copy_media("participants", f"{index + 1}.jpg", "participants")
        participants.append(
            Participant(
                name=name,
                number=index + 1,
                region=region,
                discipline_id=discipline_ids[index % len(discipline_ids)],
                photo_url=photo_url,
                bio=f"Опытный каюр из региона {region}. Участник гонки «Авача 2027».",
                dogs_count=random.Random(2027 + index).randint(4, 12),
                status=ParticipantStatus.REGISTERED.value,
            )
        )
    session.add_all(participants)
    await session.flush()
    created["Participant"] = len(participants)

    # ── Stages (все planned, статус меняет сценарий) ──
    stages = []
    for s_data in STAGES_DATA:
        start_dt = datetime.fromisoformat(s_data["start_utc"].replace("Z", "+00:00"))
        stages.append(
            Stage(
                name=f"Этап {s_data['number']}. {s_data['name']}",
                distance_km=float(s_data["distance"]),
                start_time=start_dt,
                finish_time=start_dt + timedelta(hours=s_data["duration"]),
                order_index=s_data["number"] - 1,
                tracker_interval_seconds=1200,
                status=StageStatus.PLANNED.value,
                results_publication=PublicationStatus.DRAFT.value,
                season_id=season.id,
                number=s_data["number"],
            )
        )
    session.add_all(stages)
    await session.flush()
    created["Stage"] = len(stages)

    # ── Route JSON, Checkpoints, StageRoutePoint ──
    if not ROUTE_JSON_PATH.exists():
        raise RuntimeError(f"{ROUTE_JSON_PATH} не найден. Смонтируй ./data:/app/data")

    route_json = json.loads(ROUTE_JSON_PATH.read_text(encoding="utf-8"))

    checkpoints = []
    route_points = []
    for stage in stages:
        json_stage = next(
            (js for js in route_json.get("stages", []) if js["number"] == stage.number), None
        )
        if not json_stage or not json_stage.get("coordinates"):
            raise RuntimeError(f"В JSON нет coordinates для этапа {stage.number}")
        coords = json_stage["coordinates"]  # [[lon, lat], ...]

        # Route points
        for i, (lon, lat) in enumerate(coords):
            route_points.append(
                StageRoutePoint(
                    stage_id=stage.id,
                    position=i,
                    lat=lat,
                    lon=lon,
                )
            )

        # Checkpoints — 4 на этап
        def make_cp(stage, code, name, kind, coord, order_idx):
            return Checkpoint(
                stage_id=stage.id,
                code=code,
                name=name,
                kind=kind,
                description=f"{name} (этап {stage.number})",
                lat=coord[1],
                lon=coord[0],
                altitude=100,
                km_from_race_start=0,
                order_index=order_idx,
                has_judge=True,
                is_public=True,
            )

        checkpoints.extend(
            [
                make_cp(stage, "Старт", "Старт этапа", CheckpointKind.START.value, coords[0], 0),
                make_cp(
                    stage,
                    "КП-1",
                    "Контрольный пункт 1",
                    CheckpointKind.CHECKPOINT.value,
                    coords[int(len(coords) * 0.3)],
                    1,
                ),
                make_cp(
                    stage,
                    "КП-2",
                    "Контрольный пункт 2",
                    CheckpointKind.CHECKPOINT.value,
                    coords[int(len(coords) * 0.7)],
                    2,
                ),
                make_cp(stage, "Финиш", "Финиш этапа", CheckpointKind.FINISH.value, coords[-1], 3),
            ]
        )

    session.add_all(route_points)
    session.add_all(checkpoints)
    await session.flush()
    created["StageRoutePoint"] = len(route_points)
    created["Checkpoint"] = len(checkpoints)

    # ── ScheduleEvent ──
    schedule_events = [
        ScheduleEvent(
            title="Старт этапа 1",
            description="Старт первого этапа.",
            kind=ScheduleKind.RACE.value,
            stage_id=stages[0].id,
            starts_at=datetime(2027, 3, 1, 2, 0, tzinfo=UTC),
            ends_at=datetime(2027, 3, 1, 2, 30, tzinfo=UTC),
            location="Петропавловск-Камчатский",
            is_public=True,
        ),
        ScheduleEvent(
            title="Открытие фестиваля «Авача»",
            description="Церемония открытия.",
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
    created["ScheduleEvent"] = len(schedule_events)

    # ── ViewerLocation ──
    viewer_locations = []
    for i, loc in enumerate(VIEWER_LOCATIONS):
        viewer_locations.append(
            ViewerLocation(
                name=loc["name"],
                kind=loc["kind"],
                category=loc["category"],
                glyph=loc.get("glyph", ViewerLocationGlyph.PIN.value),
                lat=loc["lat"],
                lon=loc["lon"],
                description=loc.get("description")
                or f"Зрительская площадка: {loc['name'].lower()}.",
                address="Камчатский край",
                parking_info="Бесплатная парковка у площадки.",
                facilities=["Парковка", "Пункт обогрева", "Кафе"],
                first_arrival_planned_at=now + timedelta(days=1, hours=i),
                stage_id=stages[0].id if i < 2 else None,
                safety_notes="",
                is_public=True,
            )
        )
    session.add_all(viewer_locations)
    created["ViewerLocation"] = len(viewer_locations)

    # ── NewsPost ──
    news_posts = []
    for i, title in enumerate(NEWS_TITLES):
        cover_url = _copy_media("news", f"news{i + 1}.jpg", "news")
        news_posts.append(
            NewsPost(
                title=title,
                lead=f"Кратко о событиях дня: {title.lower().rstrip('.')}.",
                body=f"Подробный репортаж. {title}. Следите за обновлениями в официальном сообществе ВКонтакте.",
                cover_url=cover_url,
                source=NewsSource.MANUAL.value,
                vk_url=None,
                stage_id=stages[0].id if i < 2 else None,
                published_at=now - timedelta(days=max(0, 2 - i // 2)),
                is_published=(i % 3 != 0),
                is_important=(i == 1),
                is_pinned=(i == 0),
            )
        )
    session.add_all(news_posts)
    created["NewsPost"] = len(news_posts)

    # ── FAQItem ──
    faq_items = [
        FAQItem(question=q, answer=a, category=c, order_index=i, is_public=True)
        for i, (q, a, c) in enumerate(FAQ_ITEMS)
    ]
    faq_items.extend(
        [
            FAQItem(question=q, answer=a, category="getting_here", order_index=i, is_public=True)
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
    created["FAQItem"] = len(faq_items)

    # ── StaticPage ──
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
        cover_url = _copy_media("pages", cover_file, "pages") if cover_file else None
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
        created["StaticPage"] = created.get("StaticPage", 0) + 1

    # ── GuestItem ──
    guest_items = [
        GuestItem(
            section="clothing",
            title="Первый слой",
            text="Качественное термобелье (синтетика или шерсть мериноса), которое отводит влагу.",
            order_index=1,
            image_url=_copy_media("guests", "clothing1.jpg", "guests"),
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
            image_url=_copy_media("guests", "shoes1.jpg", "guests"),
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
            image_url=_copy_media("guests", "equipment1.jpg", "guests"),
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
    created["GuestItem"] = len(guest_items)

    await session.flush()

    return {
        "season": season,
        "stages": stages,
        "checkpoints": checkpoints,
        "users": users,
        "admin": admin,
        "participants": participants,
        "discipline_ids": discipline_ids,
    }
