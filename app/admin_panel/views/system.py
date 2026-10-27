from markupsafe import Markup
from sqlalchemy import select
from starlette.requests import Request

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime
from app.admin_panel.utils import get_int_param
from app.db.models.admin_account import AdminAccount
from app.db.models.admin_session import AdminSession
from app.db.models.audit_log import AuditLog


class AdminAccountAdmin(BaseAdminView, model=AdminAccount):
    name = "Администратор"
    name_plural = "Администраторы"
    icon = "fa-solid fa-user-shield"
    category = CategoryAdminEnum.CATEGORY_SYSTEM
    category_icon = "fa-solid fa-gear"

    column_list = [
        AdminAccount.id,
        AdminAccount.login,
        AdminAccount.vk_user_id,
        AdminAccount.display_name,
        AdminAccount.is_active,
        AdminAccount.created_at,
    ]
    column_labels = {
        AdminAccount.id: "ID",
        AdminAccount.login: "Логин",
        AdminAccount.vk_user_id: "VK ID",
        AdminAccount.display_name: "Имя",
        AdminAccount.is_active: "Активен",
        AdminAccount.created_at: "Создан",
    }
    column_formatters = {
        AdminAccount.login: lambda m, a: Markup(
            f'<a href="/admin-panel/admin-account/details/{m.id}" class="text-primary fw-bold text-decoration-none">{m.login}</a>'
        ),
        AdminAccount.is_active: lambda m, a: fmt_bool(m.is_active),
        AdminAccount.created_at: lambda m, a: fmt_datetime(m.created_at),
    }
    column_formatters_detail = {
        AdminAccount.is_active: lambda m, a: fmt_bool(m.is_active),
        AdminAccount.created_at: lambda m, a: fmt_datetime(m.created_at),
        AdminAccount.sessions: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/admin-session/list?admin_id={m.id}" class="text-primary text-decoration-none">'
                f"Сессий: {len(m.sessions)}</a>"
            )
        ],
        AdminAccount.audit_logs: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/audit-log/list?admin_id={m.id}" class="text-primary text-decoration-none">'
                f"Записей аудита: {len(m.audit_logs)}</a>"
            )
        ],
        AdminAccount.entered_marks: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/official-mark/list?entered_by_admin_id={m.id}" class="text-primary text-decoration-none">'
                f"Внесённых отметок: {len(m.entered_marks)}</a>"
            )
        ],
    }
    # password_hash НЕ выводим в деталях — это критично для безопасности
    column_details_list = [
        AdminAccount.id,
        AdminAccount.login,
        AdminAccount.vk_user_id,
        AdminAccount.display_name,
        AdminAccount.is_active,
        AdminAccount.created_at,
        AdminAccount.sessions,
        AdminAccount.audit_logs,
        AdminAccount.entered_marks,
    ]
    column_searchable_list = [AdminAccount.login, AdminAccount.display_name]

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

    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params
        if q.get("is_active") == "true":
            stmt = stmt.where(AdminAccount.is_active.is_(True))
        elif q.get("is_active") == "false":
            stmt = stmt.where(AdminAccount.is_active.is_(False))
        return stmt


class AdminSessionAdmin(BaseAdminView, model=AdminSession):
    name = "Сессия"
    name_plural = "Сессии админов"
    icon = "fa-solid fa-key"
    category = CategoryAdminEnum.CATEGORY_SYSTEM
    category_icon = "fa-solid fa-gear"
    can_create = False
    can_edit = False

    column_selectinload = [AdminSession.admin]

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
        AdminSession.admin: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/admin-account/details/{m.admin.id}" class="text-primary fw-bold text-decoration-none">'
                f"{m.admin.login}</a>"
            )
            if m.admin
            else "—"
        ),
        AdminSession.created_at: lambda m, a: fmt_datetime(m.created_at),
        AdminSession.expires_at: lambda m, a: fmt_datetime(m.expires_at),
        AdminSession.revoked_at: lambda m, a: (
            Markup(f'<span class="text-danger fw-bold">{fmt_datetime(m.revoked_at)}</span>')
            if m.revoked_at
            else Markup('<span class="badge bg-success-lt text-success">Активна</span>')
        ),
    }
    column_formatters_detail = {
        AdminSession.admin: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/admin-account/details/{m.admin.id}" class="text-primary fw-bold text-decoration-none">'
                f"{m.admin.login} ({m.admin.display_name})</a>"
            )
            if m.admin
            else "—"
        ),
        AdminSession.created_at: lambda m, a: fmt_datetime(m.created_at),
        AdminSession.expires_at: lambda m, a: fmt_datetime(m.expires_at),
        AdminSession.revoked_at: lambda m, a: (
            Markup(f'<span class="text-danger fw-bold">{fmt_datetime(m.revoked_at)}</span>')
            if m.revoked_at
            else Markup('<span class="badge bg-success-lt text-success">Активна</span>')
        ),
    }
    column_details_list = [
        AdminSession.admin,
        AdminSession.created_at,
        AdminSession.expires_at,
        AdminSession.revoked_at,
    ]

    def list_query(self, request: Request):
        stmt = select(self.model)
        if aid := get_int_param(request, "admin_id"):
            stmt = stmt.where(AdminSession.admin_id == aid)
        return stmt


class AuditLogAdmin(BaseAdminView, model=AuditLog):
    name = "Запись аудита"
    name_plural = "Журнал аудита"
    icon = "fa-solid fa-clipboard-list"
    category = CategoryAdminEnum.CATEGORY_SYSTEM
    category_icon = "fa-solid fa-gear"
    can_create = False
    can_edit = False

    column_selectinload = [AuditLog.admin]

    column_list = [
        AuditLog.id,
        AuditLog.admin,
        AuditLog.action,
        AuditLog.entity_type,
        AuditLog.entity_id,
        AuditLog.created_at,
    ]
    column_labels = {
        AuditLog.id: "ID",
        AuditLog.admin: "Администратор",
        AuditLog.action: "Действие",
        AuditLog.entity_type: "Сущность",
        AuditLog.entity_id: "ID сущности",
        AuditLog.created_at: "Когда",
    }
    column_formatters = {
        AuditLog.admin: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/admin-account/details/{m.admin.id}" class="text-primary text-decoration-none">'
                f"{m.admin.login}</a>"
            )
            if m.admin
            else Markup('<span class="text-muted">система</span>')
        ),
        AuditLog.action: lambda m, a: Markup(
            f'<span class="badge bg-blue-lt text-blue">{m.action}</span>'
        ),
        AuditLog.entity_type: lambda m, a: (
            Markup(f'<span class="text-muted">{m.entity_type}</span>') if m.entity_type else "—"
        ),
        AuditLog.created_at: lambda m, a: fmt_datetime(m.created_at),
    }
    column_formatters_detail = {
        AuditLog.admin: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/admin-account/details/{m.admin.id}" class="text-primary fw-bold text-decoration-none">'
                f"{m.admin.login} ({m.admin.display_name})</a>"
            )
            if m.admin
            else Markup('<span class="text-muted">система</span>')
        ),
        AuditLog.action: lambda m, a: Markup(
            f'<span class="badge bg-blue-lt text-blue">{m.action}</span>'
        ),
        AuditLog.created_at: lambda m, a: fmt_datetime(m.created_at),
        AuditLog.payload: lambda m, a: (
            Markup(
                f'<pre style="margin:0;font-size:0.8rem;background:var(--tblr-bg-surface-secondary);'
                f'padding:8px;border-radius:6px;max-width:600px;overflow:auto;">'
                f"{m.payload}</pre>"
            )
            if m.payload
            else "—"
        ),
    }
    column_details_list = [
        AuditLog.id,
        AuditLog.admin,
        AuditLog.action,
        AuditLog.entity_type,
        AuditLog.entity_id,
        AuditLog.payload,
        AuditLog.created_at,
    ]
    column_sortable_list = [AuditLog.created_at]
    column_searchable_list = [AuditLog.action, AuditLog.entity_type]
    can_export = True
    column_export_list = [
        AuditLog.created_at,
        AuditLog.admin,
        AuditLog.action,
        AuditLog.entity_type,
        AuditLog.entity_id,
    ]

    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if aid := get_int_param(request, "admin_id"):
            stmt = stmt.where(AuditLog.admin_id == aid)

        if action := q.get("action"):
            stmt = stmt.where(AuditLog.action == action)

        if etype := q.get("entity_type"):
            stmt = stmt.where(AuditLog.entity_type == etype)

        return stmt
