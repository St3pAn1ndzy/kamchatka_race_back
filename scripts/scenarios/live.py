"""Сценарий 2: «Во время гонки (основной)». Например, 08 февраля 2027 г."""

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Device,
    FanSubscription,
    NotificationQueue,
    OfficialMark,
    RaceStatus,
    StageRoutePoint,
    TrackPoint,
)
from app.enums import (
    CheckpointKind,
    NotificationEventType,
    NotificationStatus,
    ParticipantStatus,
    PublicationStatus,
    RaceState,
    StageStatus,
)
from scripts.scenarios.common import seed_base


def _dedup_key(imei: str, recorded_at: datetime) -> str:
    """Генерирует уникальный ключ для точки трека"""
    raw = f"{imei}:{recorded_at.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def seed(session: AsyncSession, created: dict[str, int]) -> None:
    """Сценарий 2: Гонка идет"""
    base = await seed_base(session, created)
    users = base["users"]
    participants = base["participants"]
    stages = base["stages"]
    checkpoints = base["checkpoints"]
    admin = base["admin"]

    now = datetime.now(tz=UTC)
    stage_1 = stages[0]  # Прошедший этап
    stage_2 = stages[1]  # Текущий этап (LIVE)
    stage_3 = stages[2]  # Будущий этап

    # ═══ 1. Статусы этапов ═══
    stage_1.status = StageStatus.FINISHED.value
    stage_1.results_publication = PublicationStatus.OFFICIAL.value

    stage_2.status = StageStatus.ACTIVE.value
    stage_2.results_publication = PublicationStatus.PROVISIONAL.value

    stage_3.status = StageStatus.PLANNED.value

    # ═══ 2. Ключевое: RaceStatus = live ═══
    session.add(RaceStatus(status=RaceState.LIVE.value, current_stage_id=stage_2.id))
    created["RaceStatus"] = 1

    # ═══ 3. Меняем статусы участников ═══
    statuses = (
        [ParticipantStatus.ACTIVE.value] * 10
        + [ParticipantStatus.FINISHED.value] * 3
        + [ParticipantStatus.WITHDRAWN.value] * 1
        + [ParticipantStatus.REGISTERED.value] * 1
    )
    for i, participant in enumerate(participants):
        participant.status = statuses[i]

    # Принудительно делаем Волкова (№7) активным (он на трассе)
    volkov = next(p for p in participants if p.number == 7)
    volkov.status = ParticipantStatus.ACTIVE.value

    # ═══ 4. Выдаем трекеры (Device) ═══
    devices = [
        Device(
            iridium_number=f"{i:03d}",
            imei=f"30023456{i:07d}",
            name=f"Трекер №{i:03d}",
            participant_id=participants[i - 1].id,
            stage_id=stage_2.id,
            is_active=True,
            battery_percent=85 - i,
            sos_active=False,
            last_message_at=now - timedelta(minutes=5),
        )
        for i in range(1, len(participants) + 1)
    ]
    session.add_all(devices)
    await session.flush()
    created["Device"] = len(devices)

    # ═══ 5. Генерируем треки (TrackPoint) для Этапа 2 ═══
    route_pts = (
        (
            await session.execute(
                select(StageRoutePoint)
                .where(StageRoutePoint.stage_id == stage_2.id)
                .order_by(StageRoutePoint.position)
            )
        )
        .scalars()
        .all()
    )

    track_points = []
    points_count = 20
    track_total_km = stage_2.distance_km

    for pi, participant in enumerate(participants):
        if participant.status != ParticipantStatus.ACTIVE.value:
            continue

        device = devices[pi]

        max_ratio = 0.65 if participant.number == 7 else (pi + 1) / (len(participants) + 1) * 0.9

        last_age_min = 5 + (pi % 10) * 3

        for j in range(points_count):
            ratio = (j / (points_count - 1)) * max_ratio
            route_idx = int(ratio * (len(route_pts) - 1))
            pt = route_pts[route_idx]

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
                    stage_id=stage_2.id,
                    lat=pt.lat,
                    lon=pt.lon,
                    altitude=round(20 + ratio * 100, 1),
                    course_deg=45.0,
                    source_speed=avg_speed,
                    average_speed_kmh=avg_speed,
                    km_from_start=round(ratio * track_total_km, 2),
                    recorded_at=recorded_at,
                    is_confirmed=True,
                )
            )

    session.add_all(track_points)
    await session.flush()
    created["TrackPoint"] = len(track_points)

    last_by_device = {}
    for tp in track_points:
        if tp.device_id not in last_by_device or tp.recorded_at > last_by_device[tp.device_id]:
            last_by_device[tp.device_id] = tp.recorded_at
    for device in devices:
        if device.id in last_by_device:
            device.last_message_at = last_by_device[device.id]

    # ═══ 6. Судейские отметки (OfficialMark) ═══
    stage_1_cps = sorted(
        [cp for cp in checkpoints if cp.stage_id == stage_1.id], key=lambda c: c.order_index
    )
    stage_2_cps = sorted(
        [cp for cp in checkpoints if cp.stage_id == stage_2.id], key=lambda c: c.order_index
    )

    s1_finish = next(cp for cp in stage_1_cps if cp.kind == CheckpointKind.FINISH.value)
    s2_start = next(cp for cp in stage_2_cps if cp.kind == CheckpointKind.START.value)

    official_marks = []
    for participant in participants:
        if participant.status == ParticipantStatus.FINISHED.value:
            official_marks.append(
                OfficialMark(
                    participant_id=participant.id,
                    checkpoint_id=s1_finish.id,
                    mark_time=now - timedelta(hours=12),
                    comment="Финиш этапа 1.",
                    entered_by_admin_id=admin.id,
                )
            )
        if participant.status == ParticipantStatus.ACTIVE.value:
            official_marks.append(
                OfficialMark(
                    participant_id=participant.id,
                    checkpoint_id=s2_start.id,
                    mark_time=now - timedelta(hours=2),
                    comment="Старт этапа 2.",
                    entered_by_admin_id=admin.id,
                )
            )

    session.add_all(official_marks)
    created["OfficialMark"] = len(official_marks)

    # ═══ 7. Подписки и Уведомления ═══
    demo_user = users[0]

    fan_subs = [
        FanSubscription(user_id=demo_user.id, participant_id=volkov.id),
        FanSubscription(user_id=demo_user.id, participant_id=participants[1].id),
        FanSubscription(user_id=demo_user.id, participant_id=participants[4].id),
    ]
    session.add_all(fan_subs)
    created["FanSubscription"] = len(fan_subs)

    notifications = [
        NotificationQueue(
            user_id=demo_user.id,
            event_type=NotificationEventType.FAVORITE_UPDATE.value,
            title=f"Ваш каюр {volkov.name} на трассе",
            body=f"Участник №{volkov.number} проходит Этап 2. Следите за обновлениями на карте.",
            status=NotificationStatus.SENT.value,
            attempts=1,
            scheduled_at=now - timedelta(minutes=10),
            sent_at=now - timedelta(minutes=10),
        ),
    ]
    session.add_all(notifications)
    created["NotificationQueue"] = len(notifications)
