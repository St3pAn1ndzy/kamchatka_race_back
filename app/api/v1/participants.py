"""Участники: список, карточка, «Болею за», рейтинг поддержки."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    FanSubscriptionRepoDep,
    ParticipantRepoDep,
    get_current_user,
    get_optional_user,
)
from app.db.models.user import User
from app.enums import ParticipantStatus
from app.schemas.participants import (
    FavoriteResponse,
    ParticipantDetail,
    ParticipantListItem,
    ParticipantSupporters,
    SupporterRatingEntry,
)

router = APIRouter(prefix="/participants", tags=["participants"])


@router.get(
    "/supporters/rating",
    response_model=list[SupporterRatingEntry],
    summary="Рейтинг народной поддержки",
)
async def supporters_rating(
    participants: ParticipantRepoDep,
    fans: FanSubscriptionRepoDep,
    limit: int = Query(50, ge=1, le=200),
) -> list[SupporterRatingEntry]:
    """Топ участников по числу болельщиков с динамикой за сутки."""
    rows = await fans.rating(limit=limit)
    out: list[SupporterRatingEntry] = []
    for participant_id, cnt in rows:
        participant = await participants.get_by_id(participant_id)
        if participant is None:
            continue
        delta = await fans.delta_24h(participant_id)
        out.append(
            SupporterRatingEntry(
                participant_id=participant_id,
                name=participant.name,
                number=participant.number,
                supporters_count=cnt,
                delta_24h=delta,
            )
        )
    return out


@router.get("", response_model=list[ParticipantListItem], summary="Список участников")
async def list_participants(
    participants: ParticipantRepoDep,
    search: str | None = Query(None, description="Поиск по имени"),
    discipline_id: int | None = Query(None, gt=0),
    status_filter: ParticipantStatus | None = Query(None, alias="status"),
    sort: str = Query("bib", pattern="^(bib|name|supporters)$"),
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
) -> list[ParticipantListItem]:
    """Список участников с фильтрами, сортировкой и пагинацией."""
    rows = await participants.list_filtered(
        search=search,
        discipline_id=discipline_id,
        status=status_filter,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return [
        ParticipantListItem(
            id=p.id,
            name=p.name,
            number=p.number,
            region=p.region,
            discipline_id=p.discipline_id,
            discipline=p.discipline_ref.name if p.discipline_ref else None,
            photo_url=p.photo_url,
            status=p.status,
            dogs_count=p.dogs_count,
            supporters_count=cnt,
        )
        for p, cnt in rows
    ]


@router.get(
    "/{participant_id}",
    response_model=ParticipantDetail,
    summary="Карточка участника",
)
async def get_participant(
    participant_id: int,
    participants: ParticipantRepoDep,
) -> ParticipantDetail:
    row = await participants.get_with_supporters_count(participant_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
    participant, cnt = row
    return ParticipantDetail(
        id=participant.id,
        name=participant.name,
        number=participant.number,
        region=participant.region,
        discipline_id=participant.discipline_id,
        discipline=participant.discipline_ref.name if participant.discipline_ref else None,
        photo_url=participant.photo_url,
        status=participant.status,
        dogs_count=participant.dogs_count,
        bio=participant.bio,
        supporters_count=cnt,
    )


@router.get(
    "/{participant_id}/supporters",
    response_model=ParticipantSupporters,
    summary="Счётчик болельщиков",
)
async def get_supporters(
    participant_id: int,
    participants: ParticipantRepoDep,
    fans: FanSubscriptionRepoDep,
    user: User | None = Depends(get_optional_user),
) -> ParticipantSupporters:
    if await participants.get_by_id(participant_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
    cnt = await fans.count_by_participant(participant_id)
    is_fav = await fans.is_fan(user.id, participant_id) if user else False
    return ParticipantSupporters(
        participant_id=participant_id,
        supporters_count=cnt,
        is_favorite=is_fav,
    )


@router.post(
    "/{participant_id}/favorite",
    response_model=FavoriteResponse,
    summary="Нажать «Болею за» (идемпотентно)",
)
async def favorite_add(
    participant_id: int,
    participants: ParticipantRepoDep,
    fans: FanSubscriptionRepoDep,
    user: User = Depends(get_current_user),
) -> FavoriteResponse:
    if await participants.get_by_id(participant_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
    created = await fans.add(user.id, participant_id)
    cnt = await fans.count_by_participant(participant_id)
    return FavoriteResponse(ok=True, created=created, supporters_count=cnt)


@router.delete(
    "/{participant_id}/favorite",
    response_model=FavoriteResponse,
    summary="Убрать «Болею за»",
)
async def favorite_remove(
    participant_id: int,
    participants: ParticipantRepoDep,
    fans: FanSubscriptionRepoDep,
    user: User = Depends(get_current_user),
) -> FavoriteResponse:
    if await participants.get_by_id(participant_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
    await fans.remove(user.id, participant_id)
    cnt = await fans.count_by_participant(participant_id)
    return FavoriteResponse(ok=True, created=False, supporters_count=cnt)
