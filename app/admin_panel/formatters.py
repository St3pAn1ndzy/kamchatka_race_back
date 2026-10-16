"""Общие форматтеры для SQLAdmin.

column_formatters — словарь {поле: callable(model, attr) -> str | Markup}.
Возвращаемое значение вставляется в HTML как есть, поэтому бейджи
оборачиваем в markupsafe.Markup.
"""

from datetime import datetime

from markupsafe import Markup

from app.enums import (
    NotificationEventType,
    NotificationStatus,
    ParticipantStatus,
    PublicationStatus,
    StageStatus,
)

# --- Базовые --------------------------------------------------------------


def fmt_datetime(value: datetime | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Дата в человеческом формате. None → «—»."""
    if value is None:
        return "—"
    return value.strftime(fmt)


def fmt_date(value: datetime | None) -> str:
    return fmt_datetime(value, "%d.%m.%Y")


def fmt_bool(value: bool | None) -> Markup:
    """True → зелёная галочка, False → крестик, None → «—»."""
    if value is None:
        return Markup('<span class="text-muted">—</span>')
    if value:
        return Markup('<i class="fa-solid fa-check text-success"></i>')
    return Markup('<i class="fa-solid fa-xmark text-muted"></i>')


def fmt_badge(text: str, color: str) -> Markup:
    """Цветной бейдж Tabler.

    color: success | warning | danger | info | secondary
    """
    return Markup(f'<span class="badge bg-{color}-lt">{text}</span>')


# --- Статусы --------------------------------------------------------------


_PARTICIPANT_STATUS_MAP: dict[str, tuple[str, str]] = {
    ParticipantStatus.REGISTERED.value: ("Заявлен", "secondary"),
    ParticipantStatus.ACTIVE.value: ("Активен", "success"),
    ParticipantStatus.FINISHED.value: ("Финишировал", "info"),
    ParticipantStatus.WITHDRAWN.value: ("Сошёл", "warning"),
    ParticipantStatus.DISQUALIFIED.value: ("Дисквалифицирован", "danger"),
}


def fmt_participant_status(status: str) -> Markup:
    text, color = _PARTICIPANT_STATUS_MAP.get(status, (status, "secondary"))
    return fmt_badge(text, color)


_STAGE_STATUS_MAP: dict[str, tuple[str, str]] = {
    StageStatus.PLANNED.value: ("Запланирован", "secondary"),
    StageStatus.ACTIVE.value: ("Идёт", "success"),
    StageStatus.FINISHED.value: ("Завершён", "info"),
}


def fmt_stage_status(status: str) -> Markup:
    text, color = _STAGE_STATUS_MAP.get(status, (status, "secondary"))
    return fmt_badge(text, color)


_PUBLICATION_MAP: dict[str, tuple[str, str]] = {
    PublicationStatus.DRAFT.value: ("Черновик", "secondary"),
    PublicationStatus.PROVISIONAL.value: ("Предварительно", "warning"),
    PublicationStatus.OFFICIAL.value: ("Официально", "success"),
}


def fmt_publication(status: str) -> Markup:
    text, color = _PUBLICATION_MAP.get(status, (status, "secondary"))
    return fmt_badge(text, color)


_NOTIFICATION_STATUS_MAP: dict[str, tuple[str, str]] = {
    NotificationStatus.PENDING.value: ("В очереди", "secondary"),
    NotificationStatus.SENT.value: ("Отправлено", "success"),
    NotificationStatus.SKIPPED.value: ("Пропущено", "warning"),
    NotificationStatus.FAILED.value: ("Ошибка", "danger"),
}


def fmt_notification_status(status: str) -> Markup:
    text, color = _NOTIFICATION_STATUS_MAP.get(status, (status, "secondary"))
    return fmt_badge(text, color)


_NOTIFICATION_EVENT_MAP: dict[str, str] = {
    NotificationEventType.STAGE_START.value: "Старт этапа",
    NotificationEventType.STAGE_FINISH.value: "Финиш этапа",
    NotificationEventType.CHECKPOINT_PASSED.value: "Пройден КП",
    NotificationEventType.LEADER_CHANGED.value: "Смена лидера",
    NotificationEventType.PARTICIPANT_FINISHED.value: "Участник финишировал",
    NotificationEventType.BROADCAST.value: "Рассылка",
    NotificationEventType.FAVORITE_UPDATE.value: "Мой каюр",
}


def fmt_notification_event(event_type: str) -> str:
    return _NOTIFICATION_EVENT_MAP.get(event_type, event_type)


_NEWS_SOURCE_MAP: dict[str, tuple[str, str]] = {
    "manual": ("Вручную", "info"),
    "vk": ("ВКонтакте", "primary"),
}


def fmt_news_source(source: str) -> Markup:
    text, color = _NEWS_SOURCE_MAP.get(source, (source, "secondary"))
    return fmt_badge(text, color)


_SCHEDULE_KIND_MAP: dict[str, tuple[str, str]] = {
    "race": ("Гонка", "success"),
    "cultural": ("Культура", "info"),
    "other": ("Другое", "secondary"),
}


def fmt_schedule_kind(kind: str) -> Markup:
    text, color = _SCHEDULE_KIND_MAP.get(kind, (kind, "secondary"))
    return fmt_badge(text, color)


_VIEWER_KIND_MAP: dict[str, tuple[str, str]] = {
    "start": ("Старт", "success"),
    "finish": ("Финиш", "info"),
    "viewpoint": ("Смотровая", "primary"),
    "festival": ("Фестиваль", "warning"),
    "other": ("Другое", "secondary"),
}


def fmt_viewer_kind(kind: str) -> Markup:
    text, color = _VIEWER_KIND_MAP.get(kind, (kind, "secondary"))
    return fmt_badge(text, color)


_CHECKPOINT_KIND_MAP: dict[str, tuple[str, str]] = {
    "start": ("Старт", "success"),
    "checkpoint": ("КП", "info"),
    "finish": ("Финиш", "warning"),
}


def fmt_checkpoint_kind(kind: str) -> Markup:
    text, color = _CHECKPOINT_KIND_MAP.get(kind, (kind, "secondary"))
    return fmt_badge(text, color)
