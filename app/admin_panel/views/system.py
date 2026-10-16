"""Views для системных сущностей: админы, сессии, аудит."""

from sqladmin import ModelView

from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime
from app.db.models.admin_account import AdminAccount
from app.db.models.admin_session import AdminSession
from app.db.models.audit_log import AuditLog


class AdminAccountAdmin(ModelView, model=AdminAccount):
    name = "Администратор"
    name_plural = "Администраторы"
    icon = "fa-solid fa-user-shield"
    category = CategoryAdminEnum.CATEGORY_SYSTEM
    category_icon = "fa-solid fa-gear"
    # password_hash не показываем — даже админам.
    column_list = [
        AdminAccount.id,
        AdminAccount.login,
        AdminAccount.vk_user_id,
        AdminAccount.display_name,
        AdminAccount.is_active,
        AdminAccount.created_at,
    ]
    column_formatters = {
        AdminAccount.is_active: lambda m, a: fmt_bool(m.is_active),
    }
    column_searchable_list = [AdminAccount.login, AdminAccount.display_name]

    can_delete = False

    form_columns = [
        AdminAccount.login,
        AdminAccount.display_name,
        AdminAccount.vk_user_id,
        AdminAccount.is_active,
    ]
    form_widget_args = {
        AdminAccount.login: {"placeholder": "admin"},
        AdminAccount.display_name: {"placeholder": "Главный администратор"},
        AdminAccount.vk_user_id: {"placeholder": "123456 (опционально)"},
    }


class AdminSessionAdmin(ModelView, model=AdminSession):
    name = "Сессия"
    name_plural = "Сессии админов"
    icon = "fa-solid fa-key"
    category = CategoryAdminEnum.CATEGORY_SYSTEM
    category_icon = "fa-solid fa-gear"
    # Сессии создаются через login. Вручную — только просмотр.
    can_create = False
    can_edit = False
    column_list = [
        AdminSession.admin,
        AdminSession.created_at,
        AdminSession.expires_at,
        AdminSession.revoked_at,
    ]
    column_labels = {
        AdminSession.admin: "Администратор",
        AdminSession.created_at: "Создана",
        AdminSession.expires_at: "Истекает",
        AdminSession.revoked_at: "Отозвана",
    }
    column_formatters = {
        AdminSession.admin: lambda m, a: m.admin.login if m.admin else "—",
        AdminSession.created_at: lambda m, a: fmt_datetime(m.created_at),
        AdminSession.expires_at: lambda m, a: fmt_datetime(m.expires_at),
        AdminSession.revoked_at: lambda m, a: fmt_datetime(m.revoked_at),
    }


class AuditLogAdmin(ModelView, model=AuditLog):
    name = "Запись аудита"
    name_plural = "Журнал аудита"
    icon = "fa-solid fa-clipboard-list"
    category = CategoryAdminEnum.CATEGORY_SYSTEM
    category_icon = "fa-solid fa-gear"
    # Журнал — только просмотр.
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [
        AuditLog.id,
        AuditLog.admin,
        AuditLog.action,
        AuditLog.entity_type,
        AuditLog.entity_id,
        AuditLog.created_at,
    ]
    column_formatters = {
        AuditLog.admin: lambda m, a: m.admin.login if m.admin else "—",
    }
    column_sortable_list = [AuditLog.created_at]
    column_searchable_list = [AuditLog.action, AuditLog.entity_type]
