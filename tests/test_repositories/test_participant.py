from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import Participant
from app.enums import ParticipantStatus
from app.repositories.participant import ParticipantRepository


def _repo(results):
    session = MagicMock(spec=AsyncSession)
    session.execute.side_effect = results
    return ParticipantRepository(session), session


def _compiled(call):
    return call.args[0].compile(dialect=postgresql.dialect())


async def test_list_filtered_applies_search_discipline_status_and_supporters_order():
    """Список применяет поиск, дисциплину, статус и сортировку по поддержке"""
    participant = Participant(id=1, name="Racer", number=5)
    result = MagicMock()
    result.all.return_value = [(participant, 3)]
    repo, session = _repo([result])
    rows = await repo.list_filtered(
        search="Race",
        discipline_id=2,
        status=ParticipantStatus.ACTIVE,
        sort="supporters",
        limit=12,
        offset=4,
    )
    assert rows == [(participant, 3)]
    compiled = _compiled(session.execute.await_args)
    sql = str(compiled)
    assert "participants.name ILIKE" in sql
    assert "participants.discipline_id = " in sql
    assert "participants.status = " in sql
    assert "ORDER BY cnt DESC, participants.number ASC" in sql
    assert {"%Race%", 2, "active", 12, 4} <= set(compiled.params.values())


@pytest.mark.parametrize(
    "sort, fragment",
    [
        ("bib", "ORDER BY participants.number ASC"),
        ("name", "ORDER BY participants.name ASC"),
    ],
)
async def test_list_filtered_sort_modes(sort, fragment):
    """Сортировка по номеру или имени отражается в SQL-запросе"""
    result = MagicMock()
    result.all.return_value = []
    repo, session = _repo([result])
    await repo.list_filtered(sort=sort)
    assert fragment in str(_compiled(session.execute.await_args))


async def test_count_filtered_uses_same_filters():
    """Подсчёт участников учитывает те же фильтры, что и список"""
    result = MagicMock()
    result.scalar_one.return_value = 8
    repo, session = _repo([result])
    assert (
        await repo.count_filtered(search="Race", discipline_id=2, status=ParticipantStatus.ACTIVE)
        == 8
    )
    sql = str(_compiled(session.execute.await_args))
    assert "count(participants.id)" in sql
    assert "participants.name ILIKE" in sql
    assert "participants.discipline_id = " in sql
    assert "participants.status = " in sql


async def test_detail_returns_none_when_participant_missing():
    """Карточка отсутствующего участника возвращает None"""
    result = MagicMock()
    result.first.return_value = None
    repo, _ = _repo([result])
    assert await repo.get_with_supporters_count(99) is None


async def test_detail_returns_supporter_count():
    """Карточка существующего участника содержит число болельщиков"""
    participant = Participant(id=1, name="Racer", number=5)
    result = MagicMock()
    result.first.return_value = (participant, 7)
    repo, session = _repo([result])
    assert await repo.get_with_supporters_count(1) == (participant, 7)
    assert "participants.id = " in str(_compiled(session.execute.await_args))


async def test_map_list_requires_filter_and_skips_database_without_it():
    """Без фильтра карта возвращает пустой список без обращения к БД"""
    repo, session = _repo([])
    assert await repo.list_for_map(
        discipline_ids=None, participant_ids=None, limit=5, offset=0
    ) == ([], 0)
    session.execute.assert_not_awaited()


async def test_map_list_filters_and_paginates():
    """Список для карты фильтруется и возвращает общее число и страницу"""
    participant = Participant(id=1, name="Racer", number=5)
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [participant]
    repo, session = _repo([count_result, rows_result])
    assert await repo.list_for_map(discipline_ids=[2], participant_ids=[1], limit=5, offset=2) == (
        [participant],
        1,
    )
    queries = [_compiled(call) for call in session.execute.await_args_list]
    assert all("participants.discipline_id IN" in str(query) for query in queries)
    assert all("participants.id IN" in str(query) for query in queries)
    assert "ORDER BY participants.number, participants.id" in str(queries[1])
    assert "LIMIT" in str(queries[1])
