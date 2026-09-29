"""SQLAdmin — веб-панель администраторов."""

from sqladmin import ModelView

from app.db.models.admin_account import AdminAccount
from app.db.models.admin_session import AdminSession
from app.db.models.audit_log import AuditLog


class AdminAccountAdmin(ModelView, model=AdminAccount):
    name = "Администратор"
    name_plural = "Администраторы"
    icon = "fa-solid fa-user-shield"
    # password_hash не показываем — даже админам.
    column_list = [
        AdminAccount.id,
        AdminAccount.login,
        AdminAccount.vk_user_id,
        AdminAccount.display_name,
        AdminAccount.is_active,
        AdminAccount.created_at,
    ]
    column_searchable_list = [AdminAccount.login, AdminAccount.display_name]


class AdminSessionAdmin(ModelView, model=AdminSession):
    name = "Сессия"
    name_plural = "Сессии админов"
    icon = "fa-solid fa-key"
    # Сессии создаются через login. Вручную — только просмотр.
    can_create = False
    can_edit = False
    column_list = [
        AdminSession.id,
        AdminSession.admin_id,
        AdminSession.expires_at,
        AdminSession.revoked_at,
        AdminSession.created_at,
    ]


class AuditLogAdmin(ModelView, model=AuditLog):
    name = "Аудит"
    name_plural = "Журнал аудита"
    icon = "fa-solid fa-clipboard-list"
    # Журнал — только просмотр.
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [
        AuditLog.id,
        AuditLog.admin_id,
        AuditLog.action,
        AuditLog.entity_type,
        AuditLog.entity_id,
        AuditLog.created_at,
    ]
    column_sortable_list = [AuditLog.created_at]
    column_searchable_list = [AuditLog.action, AuditLog.entity_type]


VIEWS: list[type[ModelView]] = [
    AdminAccountAdmin,
    AdminSessionAdmin,
    AuditLogAdmin,
]
