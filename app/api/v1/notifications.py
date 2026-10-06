"""API уведомлений: история, preview."""

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, NotificationQueueRepoDep, SessionDep
from app.db.models.user import User
from app.enums import NotificationEventType
from app.schemas.notifications import (
    NotificationItem,
    NotificationListResponse,
    NotificationPreferenceOut,
    NotificationPreviewListResponse,
    NotificationPreviewResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="История уведомлений",
)
async def list_notifications(
    user: CurrentUserDep,
    queue: NotificationQueueRepoDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> NotificationListResponse:
    """Мои уведомления с пагинацией."""
    items = await queue.list_by_user(user.id, limit=limit, offset=offset)
    total = await queue.count_by_user(user.id)
    return NotificationListResponse(
        items=[NotificationItem.model_validate(item) for item in items],
        total=total,
    )


@router.get(
    "/preview",
    response_model=NotificationPreviewListResponse,
    summary="Примеры текстов уведомлений",
)
async def preview_notifications() -> NotificationPreviewListResponse:
    """Примеры — для экрана настроек уведомлений.

    Формулировки с «данные на HH:MM», без «прямо сейчас».
    """
    templates = [
        (
            NotificationEventType.STAGE_START,
            "Старт этапа",
            "Этап 1 начался. Участники на трассе.",
        ),
        (
            NotificationEventType.STAGE_FINISH,
            "Финиш этапа",
            "Этап 1 завершён. Первым финишировал Иван Петров.",
        ),
        (
            NotificationEventType.LEADER_CHANGED,
            "Смена лидера",
            "Иван Петров вышел на первое место.",
        ),
        (
            NotificationEventType.CHECKPOINT_PASSED,
            "Мой каюр на КП",
            "Иван Петров прошёл КП-3.",
        ),
        (
            NotificationEventType.PARTICIPANT_FINISHED,
            "Мой каюр финишировал",
            "Иван Петров финишировал на 2 месте.",
        ),
    ]
    return NotificationPreviewListResponse(
        items=[
            NotificationPreviewResponse(event_type=et, title=t, body=b) for et, t, b in templates
        ]
    )


# Названия типов событий. Если добавили новый event_type —
# добавь title в _EVENT_TITLES. Fallback: et.value.
_EVENT_TITLES: dict[NotificationEventType, str] = {
    NotificationEventType.CHECKPOINT_PASSED: "Мой каюр прошёл КП",
    NotificationEventType.LEADER_CHANGED: "Смена лидера",
    NotificationEventType.PARTICIPANT_FINISHED: "Мой каюр финишировал",
    NotificationEventType.STAGE_START: "Старт этапа",
    NotificationEventType.STAGE_FINISH: "Финиш этапа",
    NotificationEventType.FAVORITE_UPDATE: "Новости гонки",
}


def _build_settings(user: User) -> NotificationSettingsResponse:
    """Собрать ответ с настройками уведомлений."""
    return NotificationSettingsResponse(
        notifications_allowed=user.notifications_allowed,
        preferences=[
            NotificationPreferenceOut(
                event_type=et,
                title=_EVENT_TITLES.get(et, et.value),
                enabled=user.notifications_allowed,
            )
            for et in NotificationEventType
            if et is not NotificationEventType.BROADCAST
        ],
    )


@router.get(
    "/settings",
    response_model=NotificationSettingsResponse,
    summary="Настройки уведомлений",
)
async def get_notification_settings(
    user: CurrentUserDep,
) -> NotificationSettingsResponse:
    """Текущие настройки push-уведомлений."""
    return _build_settings(user)


@router.patch(
    "/settings",
    response_model=NotificationSettingsResponse,
    summary="Изменить настройки уведомлений",
)
async def update_notification_settings(
    body: NotificationSettingsUpdate,
    user: CurrentUserDep,
    session: SessionDep,
) -> NotificationSettingsResponse:
    """Включить или выключить push-уведомления."""
    if body.notifications_allowed is not None:
        user.notifications_allowed = body.notifications_allowed
        await session.commit()
    return _build_settings(user)
