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
from scripts.scenarios.app_scenarios_data import APP_DISCIPLINES, APP_MUSHERS
from scripts.scenarios.common import seed_base

# ═══════════════════════════════════════════════════════════════════════════
# Реальные результаты (время прохождения дистанции) из Excel дизайнеров
# ═══════════════════════════════════════════════════════════════════════════
RESULTS_DATA = {
    1: {"s1": "2:39:55", "s2": "2:40:06"},
    2: {"s1": "2:35:56", "s2": "2:42:46"},
    3: {"s1": "2:26:46", "s2": "2:44:20"},
    4: {"s1": "2:22:49", "s2": "2:32:30"},
    5: {"s1": "3:32:24", "s2": "3:38:30"},
    6: {"s1": "3:02:03", "s2": "2:56:06"},
    7: {"s1": "2:31:26", "s2": "2:30:57"},
    8: {"s1": "3:23:28", "s2": "3:02:16"},
    9: {"s1": "3:26:16", "s2": "2:51:08"},
    10: {"s1": "3:35:24", "s2": "4:17:21"},
    11: {"s1": "2:22:42", "s2": "2:52:48"},
    12: {"s1": "3:09:14", "s2": "DNF"},
    13: {"s1": "2:48:52", "s2": "2:56:28"},
    14: {"s1": "4:59:02", "s2": "4:22:01"},
    15: {"s1": "2:23:59", "s2": "2:30:53"},
    16: {"s1": "2:10:02", "s2": "2:18:53"},
    17: {"s1": "2:28:52", "s2": "2:43:30"},
    18: {"s1": "DNS", "s2": "DNS"},
    19: {"s1": "2:29:27", "s2": "2:35:37"},
    20: {"s1": "3:13:50", "s2": "3:09:05"},
    21: {"s1": "2:52:27", "s2": "2:54:50"},
}

# Штрафы из Excel: { номер_участника: { номер_этапа: штраф_в_минутах } }
PENALTIES = {
    2: {1: 6},  # Везунчикова: 6 минут на Этапе 1
    9: {2: 2},  # Егоров: 2 минуты на Этапе 2
}


def _parse_time(t_str: str) -> timedelta | None:
    """Конвертирует строку 'H:MM:SS' в timedelta"""
    if t_str in ("DNF", "DNS", "-"):
        return None
    parts = t_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
        s_float = float(s)
        return timedelta(hours=int(h), minutes=int(m), seconds=s_float)
    return None


async def seed(session: AsyncSession, created: dict[str, int]) -> None:
    base = await seed_base(
        session, created, custom_disciplines=APP_DISCIPLINES, custom_mushers=APP_MUSHERS
    )
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

    # ═══ 3. Генерируем отметки на основе реальных данных ═══
    start_cps = {cp.stage_id: cp for cp in checkpoints if cp.kind == CheckpointKind.START.value}
    finish_cps = {cp.stage_id: cp for cp in checkpoints if cp.kind == CheckpointKind.FINISH.value}

    official_marks = []
    # Время старта гонки (2 дня назад)
    base_time = now - timedelta(days=2, hours=10)

    for participant in participants:
        p_num = participant.number
        p_results = RESULTS_DATA.get(p_num, {})

        # Обновляем статус участника
        if p_results.get("s1") == "DNS":
            participant.status = ParticipantStatus.REGISTERED.value
            continue
        elif p_results.get("s2") == "DNF":
            participant.status = ParticipantStatus.WITHDRAWN.value
        else:
            participant.status = ParticipantStatus.FINISHED.value

        # Проходим по каждому этапу
        for stage in stages:
            s_num = stage.number
            time_key = f"s{s_num}"

            # Получаем штраф для этого участника на этом этапе (если есть)
            penalty = PENALTIES.get(p_num, {}).get(s_num, 0)

            if s_num <= 2:
                delta = _parse_time(p_results.get(time_key, ""))
            else:
                delta = _parse_time(p_results.get("s2", ""))
                if delta:
                    delta += timedelta(minutes=5)

            if delta is None:
                break

            stage_start = base_time + timedelta(days=stage.number - 1, hours=2)
            stage_finish = stage_start + delta

            if cp_start := start_cps.get(stage.id):
                official_marks.append(
                    OfficialMark(
                        participant_id=participant.id,
                        checkpoint_id=cp_start.id,
                        mark_time=stage_start,
                        comment=f"Старт этапа {stage.number}.",
                        entered_by_admin_id=admin.id,
                    )
                )

            if cp_finish := finish_cps.get(stage.id):
                official_marks.append(
                    OfficialMark(
                        participant_id=participant.id,
                        checkpoint_id=cp_finish.id,
                        mark_time=stage_finish,
                        penalty_minutes=penalty,
                        comment=f"Финиш этапа {stage.number}.",
                        entered_by_admin_id=admin.id,
                    )
                )

    session.add_all(official_marks)
    created["OfficialMark"] = len(official_marks)

    # ═══ 4. Баннер ═══
    next_race_news = NewsPost(
        title="Авача-2028: Регистрация открыта!",
        lead="Следующая гонка состоится в феврале 2028 года. Успейте подать заявку.",
        body="Мы рады сообщить, что прием заявок на участие в гонке «Авача-2028» официально открыт.",
        source=NewsSource.MANUAL.value,
        vk_url="https://vk.com/avacha.race",
        stage_id=None,
        published_at=now,
        is_published=True,
        is_important=True,
        is_pinned=True,
    )
    session.add(next_race_news)
    created["NewsPost"] = 1
