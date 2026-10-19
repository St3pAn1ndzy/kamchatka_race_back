from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.official_mark import OfficialMark
from app.repositories.official_mark import OfficialMarkRepository


def _repo(items=None):
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = items[0] if items else None
    result.scalars.return_value.all.return_value = items or []
    session.execute.return_value = result
    return OfficialMarkRepository(session), session


def _sql(session):
    return str(session.execute.await_args.args[0].compile(dialect=postgresql.dialect()))


async def test_get_active_is_scoped_to_participant_checkpoint_and_active_mark():
    """Активная отметка ищется по участнику и КП с исключением отменённых"""
    mark = OfficialMark(id=1)
    repo, session = _repo([mark])
    assert await repo.get_active(7, 8) is mark
    sql = _sql(session)
    assert "official_marks.participant_id = " in sql
    assert "official_marks.checkpoint_id = " in sql
    assert "official_marks.is_cancelled IS false" in sql
    assert "LIMIT" in sql


async def test_get_for_update_locks_selected_mark():
    """Запрос отметки для изменения содержит блокировку строки"""
    repo, session = _repo([OfficialMark(id=1)])
    await repo.get_for_update(1)
    assert "FOR UPDATE" in _sql(session)


@pytest.mark.parametrize("include_cancelled", [False, True])
async def test_get_for_stage_filters_cancelled_by_default(include_cancelled):
    """Отметки этапа сортируются, а отменённые включаются лишь по запросу"""
    mark = OfficialMark(id=1)
    repo, session = _repo([mark])
    assert await repo.get_for_stage(3, include_cancelled=include_cancelled) == [mark]
    sql = _sql(session)
    assert "checkpoints.stage_id = " in sql
    assert ("official_marks.is_cancelled IS false" in sql) is not include_cancelled
    assert "ORDER BY official_marks.participant_id, official_marks.mark_time" in sql


@pytest.mark.parametrize("stage_id", [None, 3])
async def test_get_for_participant_applies_optional_stage_filter(stage_id):
    """Отметки участника фильтруются по этапу, когда его ID указан"""
    repo, session = _repo()
    await repo.get_for_participant(7, stage_id)
    sql = _sql(session)
    assert "official_marks.participant_id = " in sql
    assert ("checkpoints.stage_id = " in sql) is (stage_id is not None)
    assert "official_marks.is_cancelled IS false" in sql


async def test_race_marks_exclude_cancelled_unless_explicitly_requested():
    """Общий список исключает отменённые отметки по умолчанию"""
    repo, session = _repo()
    await repo.get_all_for_race()
    assert "official_marks.is_cancelled IS false" in _sql(session)
    await repo.get_all_for_race(include_cancelled=True)
    assert "official_marks.is_cancelled IS false" not in _sql(session)
