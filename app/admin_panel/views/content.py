from sqladmin import ModelView
from wtforms import SelectField

from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import (
    fmt_bool,
    fmt_datetime,
    fmt_news_source,
    fmt_schedule_kind,
    fmt_viewer_kind,
)
from app.db.models import FAQItem, NewsPost, ScheduleEvent, ViewerLocation


class FAQItemAdmin(ModelView, model=FAQItem):
    name = "FAQ"
    name_plural = "FAQ"
    icon = "fa-solid fa-circle-question"
    category = CategoryAdminEnum.CATEGORY_CONTENT
    category_icon = "fa-solid fa-newspaper"

    column_list = [
        FAQItem.order_index,
        FAQItem.question,
        FAQItem.category,
        FAQItem.is_public,
    ]
    column_labels = {
        FAQItem.order_index: "Порядок",
        FAQItem.question: "Вопрос",
        FAQItem.category: "Категория",
        FAQItem.is_public: "Публичный",
    }
    column_formatters = {
        FAQItem.is_public: lambda m, a: fmt_bool(m.is_public),
    }
    column_default_sort = (FAQItem.order_index, False)

    form_widget_args = {
        FAQItem.question: {"placeholder": "Как добраться до старта?"},
        FAQItem.category: {"placeholder": "Транспорт / Безопасность / Проживание"},
    }


class NewsPostAdmin(ModelView, model=NewsPost):
    name = "Новость"
    name_plural = "Новости"
    icon = "fa-solid fa-newspaper"
    category = CategoryAdminEnum.CATEGORY_CONTENT
    category_icon = "fa-solid fa-newspaper"

    column_list = [
        NewsPost.published_at,
        NewsPost.title,
        NewsPost.source,
        NewsPost.stage,
        NewsPost.is_important,
        NewsPost.is_published,
        NewsPost.is_pinned,
    ]
    column_labels = {
        NewsPost.published_at: "Опубликовано",
        NewsPost.title: "Заголовок",
        NewsPost.source: "Источник",
        NewsPost.stage: "Этап",
        NewsPost.is_important: "Важная",
        NewsPost.is_published: "Опубликована",
        NewsPost.is_pinned: "Закреплена",
    }
    column_formatters = {
        NewsPost.published_at: lambda m, a: fmt_datetime(m.published_at),
        NewsPost.stage: lambda m, a: f"Этап {m.stage.number}" if m.stage else "—",
        NewsPost.is_important: lambda m, a: fmt_bool(m.is_important),
        NewsPost.is_published: lambda m, a: fmt_bool(m.is_published),
        NewsPost.is_pinned: lambda m, a: fmt_bool(m.is_pinned),
        NewsPost.source: lambda m, a: fmt_news_source(m.source),
    }
    column_default_sort = (NewsPost.published_at, True)
    column_searchable_list = [NewsPost.title]

    can_delete = False

    form_columns = [
        NewsPost.title,
        NewsPost.lead,
        NewsPost.body,
        NewsPost.cover_url,
        NewsPost.source,
        NewsPost.vk_url,
        NewsPost.stage,
        NewsPost.published_at,
        NewsPost.is_published,
        NewsPost.is_important,
        NewsPost.is_pinned,
    ]
    form_widget_args = {
        NewsPost.title: {"placeholder": "Старт «Авачи 2027» — всё готово"},
        NewsPost.lead: {"placeholder": "Краткое описание (1–2 предложения)"},
        NewsPost.body: {"placeholder": "Полный текст новости"},
        NewsPost.cover_url: {"placeholder": "https://..."},
        NewsPost.vk_url: {"placeholder": "https://vk.com/wall-..._..."},
    }
    form_overrides = {
        "source": SelectField,
    }
    form_args = {
        "source": {
            "choices": [
                ("manual", "Вручную"),
                ("vk", "Из ВКонтакте"),
            ],
        },
    }


class ScheduleEventAdmin(ModelView, model=ScheduleEvent):
    name = "Событие программы"
    name_plural = "Программа фестиваля"
    icon = "fa-solid fa-calendar-check"
    category = CategoryAdminEnum.CATEGORY_CONTENT
    category_icon = "fa-solid fa-newspaper"

    column_list = [
        ScheduleEvent.starts_at,
        ScheduleEvent.title,
        ScheduleEvent.kind,
        ScheduleEvent.stage,
        ScheduleEvent.location,
        ScheduleEvent.is_public,
    ]
    column_labels = {
        ScheduleEvent.starts_at: "Начало",
        ScheduleEvent.title: "Название",
        ScheduleEvent.kind: "Тип",
        ScheduleEvent.stage: "Этап",
        ScheduleEvent.location: "Место",
        ScheduleEvent.is_public: "Публичное",
    }
    column_formatters = {
        ScheduleEvent.starts_at: lambda m, a: fmt_datetime(m.starts_at),
        ScheduleEvent.stage: lambda m, a: f"Этап {m.stage.number}" if m.stage else "—",
        ScheduleEvent.is_public: lambda m, a: fmt_bool(m.is_public),
        ScheduleEvent.kind: lambda m, a: fmt_schedule_kind(m.kind),
    }
    column_default_sort = (ScheduleEvent.starts_at, False)
    column_searchable_list = [ScheduleEvent.title]

    can_delete = False

    form_overrides = {"kind": SelectField}
    form_args = {
        "kind": {
            "choices": [
                ("race", "Гонка"),
                ("cultural", "Культура"),
                ("other", "Другое"),
            ],
        },
    }


class ViewerLocationAdmin(ModelView, model=ViewerLocation):
    name = "Зрительская локация"
    name_plural = "Зрительские локации"
    icon = "fa-solid fa-map-location-dot"
    category = CategoryAdminEnum.CATEGORY_CONTENT
    category_icon = "fa-solid fa-newspaper"

    column_list = [
        ViewerLocation.name,
        ViewerLocation.kind,
        ViewerLocation.travel_time_minutes,
        ViewerLocation.stage,
        ViewerLocation.is_public,
    ]
    column_labels = {
        ViewerLocation.name: "Название",
        ViewerLocation.kind: "Тип",
        ViewerLocation.travel_time_minutes: "В пути, мин",
        ViewerLocation.stage: "Этап",
        ViewerLocation.is_public: "Публичная",
    }
    column_formatters = {
        ViewerLocation.stage: lambda m, a: f"Этап {m.stage.number}" if m.stage else "—",
        ViewerLocation.is_public: lambda m, a: fmt_bool(m.is_public),
        ViewerLocation.kind: lambda m, a: fmt_viewer_kind(m.kind),
    }
    column_searchable_list = [ViewerLocation.name]

    form_overrides = {"kind": SelectField}
    form_args = {
        "kind": {
            "choices": [
                ("start", "Старт"),
                ("finish", "Финиш"),
                ("viewpoint", "Смотровая"),
                ("festival", "Фестиваль"),
                ("other", "Другое"),
            ],
        },
    }
