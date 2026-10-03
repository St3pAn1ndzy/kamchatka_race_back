"""Публичные endpoints для карты гонки"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import func, select

from app.api.deps import SessionDep
from app.db.models.participant import Participant
from app.db.models.track_point import TrackPoint
from app.schemas.map import (
    MapEntryTrackPoint,
    MapEntryTrackResponse,
    MapParticipant,
    MapTrackPoint,
)

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/participants", response_model=list[MapParticipant])
async def list_map_participants(session: SessionDep) -> list[MapParticipant]:
    """Возвращаем участников с последней подтверждённой точкой для карты"""
    latest_points = (
        select(
            TrackPoint.participant_id.label("participant_id"),
            TrackPoint.lat.label("lat"),
            TrackPoint.lon.label("lon"),
            TrackPoint.recorded_at.label("recorded_at"),
            TrackPoint.received_at.label("received_at"),
            TrackPoint.course_deg.label("course_deg"),
            TrackPoint.source_speed.label("source_speed"),
            TrackPoint.average_speed_kmh.label("average_speed_kmh"),
            TrackPoint.km_from_start.label("km_from_start"),
            func.row_number()
            .over(
                partition_by=TrackPoint.participant_id,
                order_by=(TrackPoint.recorded_at.desc(), TrackPoint.id.desc()),
            )
            .label("row_number"),
        )
        .where(
            TrackPoint.participant_id.is_not(None),
            TrackPoint.is_confirmed.is_(True),
        )
        .subquery()
    )

    stmt = (
        select(
            Participant,
            latest_points.c.lat,
            latest_points.c.lon,
            latest_points.c.recorded_at,
            latest_points.c.received_at,
            latest_points.c.course_deg,
            latest_points.c.source_speed,
            latest_points.c.average_speed_kmh,
            latest_points.c.km_from_start,
        )
        .outerjoin(
            latest_points,
            (latest_points.c.participant_id == Participant.id) & (latest_points.c.row_number == 1),
        )
        .order_by(Participant.number.asc())
    )

    rows = (await session.execute(stmt)).all()

    items: list[MapParticipant] = []
    for row in rows:
        participant = row[0]

        # Если точки ещё нет, участник всё равно нужен карте для списка и фильтров
        latest_point = None
        if row.lat is not None and row.lon is not None:
            latest_point = MapTrackPoint(
                lat=row.lat,
                lon=row.lon,
                recorded_at=row.recorded_at,
                received_at=row.received_at,
                course_deg=row.course_deg,
                source_speed=row.source_speed,
                average_speed_kmh=row.average_speed_kmh,
                km_from_start=row.km_from_start,
            )

        items.append(
            MapParticipant(
                id=participant.id,
                name=participant.name,
                number=participant.number,
                region=participant.region,
                discipline=participant.discipline,
                photo_url=participant.photo_url,
                status=participant.status,
                latest_point=latest_point,
            )
        )

    return items


@router.get("/entry/{entry_id}/track", response_model=MapEntryTrackResponse)
async def get_entry_track(
    entry_id: Annotated[int, Path(gt=0)],
    session: SessionDep,
) -> MapEntryTrackResponse:
    """Возвращаем подтверждённый трек участника для карты"""
    participant = await session.get(Participant, entry_id)
    if participant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Участник не найден",
        )

    stmt = (
        select(TrackPoint)
        .where(
            TrackPoint.participant_id == entry_id,
            TrackPoint.is_confirmed.is_(True),
        )
        .order_by(TrackPoint.recorded_at.asc(), TrackPoint.id.asc())
    )
    points = list((await session.execute(stmt)).scalars().all())

    return MapEntryTrackResponse(
        participant_id=entry_id,
        points=[
            MapEntryTrackPoint(
                id=point.id,
                stage_id=point.stage_id,
                lat=point.lat,
                lon=point.lon,
                altitude=point.altitude,
                course_deg=point.course_deg,
                source_speed=point.source_speed,
                average_speed_kmh=point.average_speed_kmh,
                km_from_start=point.km_from_start,
                recorded_at=point.recorded_at,
                received_at=point.received_at,
            )
            for point in points
        ],
    )
