"""Сервис результатов: расчёт протоколов и сводной из OfficialMark.

Вся логика:
- Расчёт времени этапа: elapsed = finish - start
- Итоговое время: final = elapsed + штрафы(сек) - обязательные_остановки(сек)
- Приоритет у судейских отметок (требование брифа).
- draft-черновики не показываются в публичном API.
"""

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.official_mark import OfficialMark
from app.db.models.participant import Participant
from app.db.models.stage import Stage
from app.enums import CheckpointKind, PublicationStatus
from app.repositories.official_mark import OfficialMarkRepository
from app.schemas.results import (
    ControlTimeEntry,
    LeaderboardEntry,
    RaceStandings,
    StageProtocol,
    StageProtocolRow,
    StandingRow,
)

logger = logging.getLogger("avacha.results")


class ResultService:
    """Расчёт результатов на лету из OfficialMark."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.mark_repo = OfficialMarkRepository(session)

    # ── Протокол этапа ─────────────────────────────────────────────────

    async def get_stage_protocol(self, stage_id: int) -> StageProtocol | None:
        """Протокол этапа. None если этап не найден или publication=draft."""
        stage = await self.session.get(Stage, stage_id)
        if stage is None:
            return None
        # draft не показываем в публичном API
        if stage.results_publication == PublicationStatus.DRAFT.value:
            return None

        marks = await self.mark_repo.get_for_stage(stage_id)

        # Группируем отметки по участникам
        participant_marks: dict[int, list[OfficialMark]] = {}
        for m in marks:
            participant_marks.setdefault(m.participant_id, []).append(m)

        rows: list[StageProtocolRow] = []
        for _, p_marks in participant_marks.items():
            participant = p_marks[0].participant
            if participant is None:
                continue

            start_mark = next(
                (
                    m
                    for m in p_marks
                    if m.checkpoint and m.checkpoint.kind == CheckpointKind.START.value
                ),
                None,
            )
            finish_mark = next(
                (
                    m
                    for m in p_marks
                    if m.checkpoint and m.checkpoint.kind == CheckpointKind.FINISH.value
                ),
                None,
            )

            elapsed = None
            if start_mark and finish_mark:
                elapsed = int((finish_mark.mark_time - start_mark.mark_time).total_seconds())

            penalty_sec = sum(m.penalty_minutes for m in p_marks) * 60
            stop_sec = sum(m.mandatory_stop_minutes for m in p_marks) * 60

            final = None
            if elapsed is not None:
                final = elapsed + penalty_sec - stop_sec
                if final < 0:
                    final = 0

            rows.append(
                StageProtocolRow(
                    participant_id=participant.id,
                    participant_name=participant.name,
                    participant_number=participant.number,
                    start_time=start_mark.mark_time if start_mark else None,
                    finish_time=finish_mark.mark_time if finish_mark else None,
                    elapsed_time_seconds=elapsed,
                    total_penalty_seconds=penalty_sec,
                    total_mandatory_stop_seconds=stop_sec,
                    final_time_seconds=final,
                )
            )

        # Сортировка: финишировавшие по возрастанию final_time, затем нефинишировавшие
        rows.sort(key=lambda r: (r.final_time_seconds is None, r.final_time_seconds or 0))

        position = 0
        for row in rows:
            if row.final_time_seconds is not None:
                position += 1
                row.position = position

        return StageProtocol(
            stage_id=stage.id,
            stage_name=stage.name,
            publication=PublicationStatus(stage.results_publication),
            rows=rows,
        )

    # ── Сводная таблица лидеров ────────────────────────────────────────

    async def get_standings(self) -> RaceStandings:
        """Сводная таблица — сумма этапов с publication=(provisional|official)."""
        stages = await self._get_published_stages()
        if not stages:
            return RaceStandings(mode="official", rows=[])

        # Собираем протоколы всех опубликованных этапов
        all_rows: list[StageProtocolRow] = []
        for stage in stages:
            protocol = await self.get_stage_protocol(stage.id)
            if protocol is None:
                continue
            all_rows.extend(protocol.rows)

        # Группируем по участникам
        aggregated: dict[int, list[StageProtocolRow]] = {}
        for row in all_rows:
            aggregated.setdefault(row.participant_id, []).append(row)

        # 🔴 N+1 fix: один запрос вместо N
        participant_ids = list(aggregated.keys())
        participants_map: dict[int, Participant] = {}
        if participant_ids:
            stmt = select(Participant).where(Participant.id.in_(participant_ids))
            for p in (await self.session.execute(stmt)).scalars().all():
                participants_map[p.id] = p

        standing_rows: list[StandingRow] = []
        for participant_id, rows in aggregated.items():
            participant = participants_map.get(participant_id)
            if participant is None:
                continue

            total_final = 0
            stages_finished = 0
            total_penalty = 0
            total_stop = 0

            for r in rows:
                if r.final_time_seconds is not None:
                    total_final += r.final_time_seconds
                    stages_finished += 1
                total_penalty += r.total_penalty_seconds
                total_stop += r.total_mandatory_stop_seconds

            standing_rows.append(
                StandingRow(
                    participant_id=participant.id,
                    participant_name=participant.name,
                    participant_number=participant.number,
                    total_penalty_seconds=total_penalty,
                    total_mandatory_stop_seconds=total_stop,
                    final_time_seconds=total_final if stages_finished > 0 else None,
                    stages_finished=stages_finished,
                )
            )

        # Сортировка: по сумме final_time, None — в конец
        standing_rows.sort(key=lambda r: (r.final_time_seconds is None, r.final_time_seconds or 0))

        position = 0
        for row in standing_rows:
            if row.final_time_seconds is not None:
                position += 1
                row.position = position

        return RaceStandings(mode="official", rows=standing_rows)

    # ── Таблица лидеров (краткая) ──────────────────────────────────────

    async def get_leaderboard(
        self,
        limit: int = 50,
    ) -> list[LeaderboardEntry]:
        """Таблица лидеров.

        mode=official — из OfficialMark (опубликованные этапы).
        mode=live — TODO: из трекера (следующий эпик).
        """
        standings = await self.get_standings()
        entries: list[LeaderboardEntry] = []
        for row in standings.rows[:limit]:
            entries.append(
                LeaderboardEntry(
                    participant_id=row.participant_id,
                    participant_name=row.participant_name,
                    participant_number=row.participant_number,
                    position=row.position or 0,
                    final_time_seconds=row.final_time_seconds,
                    stages_finished=row.stages_finished,
                    mode="official",
                )
            )
        return entries

    # ── Отметки участника ──────────────────────────────────────────────

    async def get_control_times(
        self,
        participant_id: int,
        stage_id: int | None = None,
    ) -> list[ControlTimeEntry]:
        """Все отметки участника (по этапу или по всем).

        HTTP 404 если участник не найден (прокидывается в роутер).
        """
        participant = await self.session.get(Participant, participant_id)
        if participant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Participant not found",
            )
        marks = await self.mark_repo.get_for_participant(
            participant_id,
            stage_id=stage_id,
        )
        return [
            ControlTimeEntry(
                checkpoint_id=m.checkpoint_id,
                checkpoint_code=m.checkpoint.code if m.checkpoint else "",
                checkpoint_name=m.checkpoint.name if m.checkpoint else "",
                checkpoint_kind=m.checkpoint.kind if m.checkpoint else "",
                mark_time=m.mark_time,
                penalty_minutes=m.penalty_minutes,
                mandatory_stop_minutes=m.mandatory_stop_minutes,
            )
            for m in marks
        ]

    # ── Вспомогательные ────────────────────────────────────────────────

    async def _get_published_stages(self) -> list[Stage]:
        """Этапы с publication=provisional или official, опционально по гонке."""
        stmt = (
            select(Stage)
            .where(
                Stage.results_publication.in_(
                    [
                        PublicationStatus.PROVISIONAL.value,
                        PublicationStatus.OFFICIAL.value,
                    ]
                )
            )
            .order_by(Stage.order_index)
        )

        return list((await self.session.execute(stmt)).scalars().all())
