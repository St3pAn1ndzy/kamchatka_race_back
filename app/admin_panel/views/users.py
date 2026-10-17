from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime
from app.db.models import User


class UserAdmin(BaseAdminView, model=User):
    name = "Болельщик"
    name_plural = "Болельщики"
    icon = "fa-solid fa-user-circle"
    category = CategoryAdminEnum.CATEGORY_USERS
    category_icon = "fa-solid fa-circle-user"

    can_create = False
    can_edit = False

    column_list = [
        User.vk_user_id,
        User.first_name,
        User.last_name,
        User.notifications_allowed,
        User.is_favorite_app,
        User.consent_version,
        User.created_at,
        User.last_seen_at,
    ]
    column_labels = {
        User.vk_user_id: "VK ID",
        User.first_name: "Имя",
        User.last_name: "Фамилия",
        User.notifications_allowed: "Push",
        User.is_favorite_app: "В избранном",
        User.consent_version: "Согласие",
        User.created_at: "Создан",
        User.last_seen_at: "Активность",
    }
    column_formatters = {
        User.notifications_allowed: lambda m, a: fmt_bool(m.notifications_allowed),
        User.is_favorite_app: lambda m, a: fmt_bool(m.is_favorite_app),
        User.created_at: lambda m, a: fmt_datetime(m.created_at),
        User.last_seen_at: lambda m, a: fmt_datetime(m.last_seen_at),
    }
    column_default_sort = (User.created_at, True)
    column_searchable_list = [User.first_name, User.last_name]

    can_export = True
    column_export_list = [
        User.vk_user_id,
        User.first_name,
        User.last_name,
        User.notifications_allowed,
        User.created_at,
    ]
