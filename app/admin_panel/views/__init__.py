"""Все ModelView админ-панели, собранные в один список."""

from app.admin_panel.views.communications import (
    FanSubscriptionAdmin,
    NotificationQueueAdmin,
)
from app.admin_panel.views.content import (
    FAQItemAdmin,
    NewsPostAdmin,
    ScheduleEventAdmin,
    ViewerLocationAdmin,
)
from app.admin_panel.views.event import (
    CheckpointAdmin,
    DisciplineAdmin,
    SeasonAdmin,
    StageAdmin,
)
from app.admin_panel.views.participants import (
    DeviceAdmin,
    ParticipantAdmin,
)
from app.admin_panel.views.results import (
    OfficialMarkAdmin,
    TrackPointAdmin,
)
from app.admin_panel.views.system import (
    AdminAccountAdmin,
    AdminSessionAdmin,
    AuditLogAdmin,
)
from app.admin_panel.views.users import UserAdmin

VIEWS = [
    # Система
    AdminAccountAdmin,
    AdminSessionAdmin,
    AuditLogAdmin,
    # Событие
    SeasonAdmin,
    DisciplineAdmin,
    StageAdmin,
    CheckpointAdmin,
    # Участники
    ParticipantAdmin,
    DeviceAdmin,
    # Результаты
    OfficialMarkAdmin,
    TrackPointAdmin,
    # Контент
    NewsPostAdmin,
    ScheduleEventAdmin,
    FAQItemAdmin,
    ViewerLocationAdmin,
    # Коммуникации
    FanSubscriptionAdmin,
    NotificationQueueAdmin,
    # Пользователи
    UserAdmin,
]
