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
from app.admin_panel.views.content_admin import ContentAdminView
from app.admin_panel.views.dashboard import DashboardView
from app.admin_panel.views.event import (
    CheckpointAdmin,
    DisciplineAdmin,
    SeasonAdmin,
    StageAdmin,
)
from app.admin_panel.views.participant_card import ParticipantCardView
from app.admin_panel.views.participants import (
    DeviceAdmin,
    ParticipantAdmin,
)
from app.admin_panel.views.push_sender import PushSenderView
from app.admin_panel.views.race_control import RaceControlView
from app.admin_panel.views.race_route import RaceRouteView
from app.admin_panel.views.results import (
    OfficialMarkAdmin,
    TrackPointAdmin,
)
from app.admin_panel.views.results_admin import ResultsAdminView
from app.admin_panel.views.static_pages import StaticPageAdmin
from app.admin_panel.views.statistics_view import StatisticsView
from app.admin_panel.views.system import (
    AdminAccountAdmin,
    AdminSessionAdmin,
    AuditLogAdmin,
)
from app.admin_panel.views.tracker_monitor import TrackerMonitorView
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
    # Кастомные
    DashboardView,
    TrackerMonitorView,
    RaceControlView,
    PushSenderView,
    RaceRouteView,
    ParticipantCardView,
    ResultsAdminView,
    ContentAdminView,
    StatisticsView,
    StaticPageAdmin,
]
