"""Схемы участников и «Болею за»."""

from app.enums import ParticipantStatus
from app.schemas.base import BaseSchema


class ParticipantListItem(BaseSchema):
    """Короткая карточка участника для списка."""

    id: int
    name: str
    number: int
    region: str | None = None
    discipline_id: int | None = None
    discipline: str | None = None
    photo_url: str | None = None
    status: ParticipantStatus
    dogs_count: int | None = None
    supporters_count: int = 0


class ParticipantDetail(BaseSchema):
    """Полная карточка участника."""

    id: int
    name: str
    number: int
    region: str | None = None
    discipline_id: int | None = None
    discipline: str | None = None
    photo_url: str | None = None
    status: ParticipantStatus
    dogs_count: int | None = None
    bio: str | None = None
    supporters_count: int = 0


class ParticipantSupporters(BaseSchema):
    """Счётчик болельщиков участника."""

    participant_id: int
    supporters_count: int
    is_favorite: bool = False


class SupporterRatingEntry(BaseSchema):
    """Строка рейтинга народной поддержки."""

    participant_id: int
    name: str
    number: int
    supporters_count: int
    delta_24h: int = 0


class FavoriteResponse(BaseSchema):
    """Ответ на «Болею за» / отписку."""

    ok: bool = True
    created: bool = False
    supporters_count: int
