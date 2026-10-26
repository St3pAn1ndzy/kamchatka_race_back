from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.checkpoint import Checkpoint
from app.db.models.official_mark import OfficialMark
from app.db.models.participant import Participant
from app.db.models.stage import Stage
from app.enums import CheckpointKind, PublicationStatus
from app.schemas.results import RaceStandings, StageProtocol, StageProtocolRow, StandingRow
from app.services.results import ResultService

START_TIME = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


def _stage(stage_id: int = 1, publication: PublicationStatus = PublicationStatus.OFFICIAL) -> Stage:
    return Stage(id=stage_id, name=f"Этап {stage_id}", results_publication=publication.value)


def _participant(participant_id: int, number: int) -> Participant:
    return Participant(id=participant_id, name=f"Участник {participant_id}", number=number)


def _mark(
    participant: Participant,
    checkpoint_id: int,
    kind: CheckpointKind,
    minute: int,
    *,
    penalty: int = 0,
    stop: int = 0,
) -> OfficialMark:
    checkpoint = Checkpoint(
        id=checkpoint_id,
        stage_id=1,
        code=f"CP-{checkpoint_id}",
        name=f"КП {checkpoint_id}",
        kind=kind.value,
        lat=0.0,
        lon=0.0,
    )
    mark = OfficialMark(
        participant_id=participant.id,
        checkpoint_id=checkpoint_id,
        mark_time=START_TIME + timedelta(minutes=minute),
        penalty_minutes=penalty,
        mandatory_stop_minutes=stop,
        entered_by_admin_id=1,
    )
    mark.participant = participant
    mark.checkpoint = checkpoint
    return mark


def _service() -> tuple[ResultService, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    service = ResultService(session)
    service.mark_repo.get_for_stage = AsyncMock(return_value=[])
    service.mark_repo.get_for_participant = AsyncMock(return_value=[])
    return service, session


@pytest.mark.asyncio
async def test_stage_protocol_returns_none_for_missing_stage() -> None:
    """Несуществующий этап → None (роутер отдаст 404)."""
    service, session = _service()
    session.get.return_value = None

    assert await service.get_stage_protocol(1) is None

    session.get.assert_awaited_once_with(Stage, 1)
    service.mark_repo.get_for_stage.assert_not_awaited()


@pytest.mark.asyncio
async def test_stage_protocol_returns_empty_protocol_for_draft_stage() -> None:
    """DRAFT-этап → протокол с publication=draft и пустыми rows (не None)."""
    service, session = _service()
    session.get.return_value = _stage(publication=PublicationStatus.DRAFT)

    protocol = await service.get_stage_protocol(1)

    assert protocol is not None
    assert protocol.stage_id == 1
    assert protocol.publication == PublicationStatus.DRAFT
    assert protocol.rows == []

    session.get.assert_awaited_once_with(Stage, 1)
    # Для DRAFT выходим до запроса отметок
    service.mark_repo.get_for_stage.assert_not_awaited()


@pytest.mark.asyncio
async def test_stage_protocol_calculates_adjustments_and_positions() -> None:
    service, session = _service()
    session.get.return_value = _stage()
    fast = _participant(2, 20)
    slow = _participant(1, 10)
    unfinished = _participant(3, 30)
    service.mark_repo.get_for_stage.return_value = [
        _mark(slow, 1, CheckpointKind.START, 0),
        _mark(slow, 2, CheckpointKind.FINISH, 70),
        _mark(fast, 1, CheckpointKind.START, 0, penalty=5),
        _mark(fast, 3, CheckpointKind.CHECKPOINT, 30, penalty=2, stop=3),
        _mark(fast, 2, CheckpointKind.FINISH, 60),
        _mark(unfinished, 1, CheckpointKind.START, 0, penalty=1),
    ]

    protocol = await service.get_stage_protocol(1)

    assert protocol is not None
    assert protocol.publication == PublicationStatus.OFFICIAL
    assert [row.participant_id for row in protocol.rows] == [2, 1, 3]
    assert [row.position for row in protocol.rows] == [1, 2, None]
    assert protocol.rows[0].elapsed_time_seconds == 3600
    assert protocol.rows[0].total_penalty_seconds == 420
    assert protocol.rows[0].total_mandatory_stop_seconds == 180
    assert protocol.rows[0].final_time_seconds == 3840
    assert protocol.rows[2].final_time_seconds is None
    assert protocol.rows[2].total_penalty_seconds == 60
    service.mark_repo.get_for_stage.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_stage_protocol_never_returns_negative_final_time() -> None:
    service, session = _service()
    session.get.return_value = _stage(publication=PublicationStatus.PROVISIONAL)
    participant = _participant(1, 10)
    service.mark_repo.get_for_stage.return_value = [
        _mark(participant, 1, CheckpointKind.START, 0),
        _mark(participant, 2, CheckpointKind.FINISH, 1, stop=5),
    ]

    protocol = await service.get_stage_protocol(1)

    assert protocol is not None
    assert protocol.publication == PublicationStatus.PROVISIONAL
    assert protocol.rows[0].elapsed_time_seconds == 60
    assert protocol.rows[0].final_time_seconds == 0


@pytest.mark.asyncio
async def test_published_stage_without_marks_has_empty_protocol() -> None:
    service, session = _service()
    session.get.return_value = _stage()

    protocol = await service.get_stage_protocol(1)

    assert protocol is not None
    assert protocol.rows == []
    service.mark_repo.get_for_stage.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_standings_without_published_stages_are_empty() -> None:
    service, session = _service()
    service._get_published_stages = AsyncMock(return_value=[])

    standings = await service.get_standings()

    assert standings.mode == "official"
    assert standings.rows == []
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_standings_sum_published_stage_results_and_rank_participants() -> None:
    service, session = _service()
    service._get_published_stages = AsyncMock(return_value=[_stage(1), _stage(2)])
    service.get_stage_protocol = AsyncMock(
        side_effect=[
            StageProtocol(
                stage_id=1,
                stage_name="Этап 1",
                publication=PublicationStatus.OFFICIAL,
                rows=[
                    StageProtocolRow(
                        participant_id=1,
                        participant_name="Участник 1",
                        participant_number=10,
                        final_time_seconds=200,
                        total_penalty_seconds=60,
                        total_mandatory_stop_seconds=0,
                    ),
                    StageProtocolRow(
                        participant_id=2,
                        participant_name="Участник 2",
                        participant_number=20,
                        final_time_seconds=150,
                        total_penalty_seconds=0,
                        total_mandatory_stop_seconds=30,
                    ),
                ],
            ),
            StageProtocol(
                stage_id=2,
                stage_name="Этап 2",
                publication=PublicationStatus.PROVISIONAL,
                rows=[
                    StageProtocolRow(
                        participant_id=1,
                        participant_name="Участник 1",
                        participant_number=10,
                        final_time_seconds=100,
                        total_penalty_seconds=30,
                        total_mandatory_stop_seconds=10,
                    ),
                    StageProtocolRow(
                        participant_id=2,
                        participant_name="Участник 2",
                        participant_number=20,
                        final_time_seconds=300,
                        total_penalty_seconds=0,
                        total_mandatory_stop_seconds=0,
                    ),
                ],
            ),
        ]
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [_participant(1, 10), _participant(2, 20)]
    session.execute.return_value = result

    standings = await service.get_standings()

    assert [row.participant_id for row in standings.rows] == [1, 2]
    assert [row.position for row in standings.rows] == [1, 2]
    assert [row.final_time_seconds for row in standings.rows] == [300, 450]
    assert [row.stages_finished for row in standings.rows] == [2, 2]
    assert standings.rows[0].total_penalty_seconds == 90
    assert standings.rows[0].total_mandatory_stop_seconds == 10
    service.get_stage_protocol.assert_any_await(1)
    service.get_stage_protocol.assert_any_await(2)
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_published_stage_query_excludes_drafts() -> None:
    service, session = _service()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    assert await service._get_published_stages() == []

    statement = session.execute.call_args.args[0]
    sql = str(
        statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "'provisional'" in sql
    assert "'official'" in sql
    assert "'draft'" not in sql
    assert "ORDER BY stages.order_index" in sql


@pytest.mark.asyncio
async def test_leaderboard_respects_limit_and_keeps_official_mode() -> None:
    service, _ = _service()
    service.get_standings = AsyncMock(
        return_value=RaceStandings(
            rows=[
                StandingRow(
                    participant_id=1,
                    participant_name="Участник 1",
                    participant_number=10,
                    final_time_seconds=300,
                    position=1,
                    stages_finished=2,
                ),
                StandingRow(
                    participant_id=2,
                    participant_name="Участник 2",
                    participant_number=20,
                    final_time_seconds=450,
                    position=2,
                    stages_finished=2,
                ),
            ]
        )
    )

    entries = await service.get_leaderboard(limit=1)

    assert len(entries) == 1
    assert entries[0].participant_id == 1
    assert entries[0].final_time_seconds == 300
    assert entries[0].mode == "official"
    service.get_standings.assert_awaited_once()


@pytest.mark.asyncio
async def test_control_times_require_existing_participant() -> None:
    service, session = _service()
    session.get.return_value = None

    with pytest.raises(HTTPException) as error:
        await service.get_control_times(42)

    assert error.value.status_code == 404
    service.mark_repo.get_for_participant.assert_not_awaited()


@pytest.mark.asyncio
async def test_control_times_use_stage_filter_and_checkpoint_details() -> None:
    service, session = _service()
    participant = _participant(1, 10)
    session.get.return_value = participant
    service.mark_repo.get_for_participant.return_value = [
        _mark(participant, 3, CheckpointKind.CHECKPOINT, 30, penalty=2, stop=1)
    ]

    entries = await service.get_control_times(1, stage_id=1)

    assert len(entries) == 1
    assert entries[0].checkpoint_code == "CP-3"
    assert entries[0].checkpoint_name == "КП 3"
    assert entries[0].checkpoint_kind == CheckpointKind.CHECKPOINT
    assert entries[0].mark_time == START_TIME + timedelta(minutes=30)
    assert entries[0].penalty_minutes == 2
    assert entries[0].mandatory_stop_minutes == 1
    service.mark_repo.get_for_participant.assert_awaited_once_with(1, stage_id=1)
