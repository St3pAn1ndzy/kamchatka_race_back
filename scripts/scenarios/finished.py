"""Сценарий 3: «После окончания гонки». Например, 17 февраля 2027 г."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    NewsPost,
    OfficialMark,
    RaceStatus,
)
from app.enums import (
    CheckpointKind,
    NewsSource,
    ParticipantStatus,
    PublicationStatus,
    RaceState,
    StageStatus,
)
from scripts.scenarios.common import seed_base


async def seed(session: AsyncSession, created: dict[str, int]) -> None:
    """Гонка завершена:
    - RaceStatus = finished
    - Все Stage = finished, результаты опубликованы (OFFICIAL)
    - Все Participant = finished
    - Проставлены OfficialMark для финиша каждого этапа
    - Добавлен баннер (NewsPost) про следующую гонку
    """
    base = await seed_base(session, created)
    participants = base["participants"]
    stages = base["stages"]
    checkpoints = base["checkpoints"]
    admin = base["admin"]

    now = datetime.now(tz=UTC)

    # ═══ 1. Закрываем все этапы ═══
    for stage in stages:
        stage.status = StageStatus.FINISHED.value
        stage.results_publication = PublicationStatus.OFFICIAL.value

    # ═══ 2. Ключевое: RaceStatus = finished ═══
    session.add(RaceStatus(status=RaceState.FINISHED.value, current_stage_id=None))
    created["RaceStatus"] = 1

    # ═══ 3. Все участники финишировали ═══
    for participant in participants:
        participant.status = ParticipantStatus.FINISHED.value

    # ═══ 4. Генерируем финишные отметки (OfficialMark) ═══
    # Нам нужны финишные чекпоинты для каждого этапа
    finish_cps = {cp.stage_id: cp for cp in checkpoints if cp.kind == CheckpointKind.FINISH.value}

    official_marks = []

    # Базовое время финиша (например, гонка закончилась 2 дня назад)
    base_time = now - timedelta(days=2)

    for pi, participant in enumerate(participants):
        # Формируем время так, чтобы 1-й участник был самым быстрым,
        # а каждый следующий отставал на определенное количество минут
        participant_offset_minutes = (pi * 15) + (pi * pi)  # Сделает разрыв реалистичным

        for stage in stages:
            cp_finish = finish_cps.get(stage.id)
            if not cp_finish:
                continue

            # Время финиша для конкретного этапа
            mark_time = base_time + timedelta(
                days=stage.number, hours=2, minutes=participant_offset_minutes
            )

            official_marks.append(
                OfficialMark(
                    participant_id=participant.id,
                    checkpoint_id=cp_finish.id,
                    mark_time=mark_time,
                    penalty_minutes=0,
                    mandatory_stop_minutes=0,
                    comment=f"Финиш этапа {stage.number}.",
                    entered_by_admin_id=admin.id,
                    is_cancelled=False,
                )
            )

    session.add_all(official_marks)
    created["OfficialMark"] = len(official_marks)

    # ═══ 5. Баннер про следующую гонку (Авача-2028) ═══
    # Скриншот просит анонс, сделаем это через закрепленную новость
    next_race_news = NewsPost(
        title="Авача-2028: Регистрация открыта!",
        lead="Следующая гонка состоится в феврале 2028 года. Успейте подать заявку.",
        body="Мы рады сообщить, что прием заявок на участие в гонке «Авача-2028» официально открыт. Ждем сильнейших каюров со всей страны!",
        cover_url=None,
        source=NewsSource.MANUAL.value,
        vk_url="https://vk.com/avacha.race",
        stage_id=None,
        published_at=now,
        is_published=True,
        is_important=True,  # Чтобы баннер выделялся
        is_pinned=True,  # Закрепляем наверху
    )
    session.add(next_race_news)
    created["NewsPost"] = 1
