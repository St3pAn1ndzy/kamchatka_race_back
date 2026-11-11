from datetime import UTC, datetime

from markupsafe import Markup
from sqladmin import action
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import RedirectResponse
from wtforms import FileField, SelectField

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import (
    fmt_bool,
    fmt_datetime,
    fmt_news_source,
    fmt_schedule_kind,
    fmt_viewer_kind,
)
from app.admin_panel.utils import get_int_param
from app.db.base import async_session_factory
from app.db.models import AuditLog, FAQItem, NewsPost, ScheduleEvent, ViewerLocation
from app.enums import ViewerLocationCategory
from app.security.admin_sessions import get_active_admin_for_session
from app.services.cache import cache
from app.services.media_storage import media_storage


class UploadImageField(FileField):
    def populate_obj(self, obj, name):
        pass


class FAQItemAdmin(BaseAdminView, model=FAQItem):
    name = "FAQ"
    name_plural = "FAQ"
    icon = "fa-solid fa-circle-question"
    category = CategoryAdminEnum.CATEGORY_CONTENT
    category_icon = "fa-solid fa-newspaper"
    can_delete = True

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
        FAQItem.category: lambda m, a: (
            Markup(f'<span class="badge bg-blue-lt text-blue">{m.category}</span>')
            if m.category
            else "—"
        ),
    }
    column_formatters_detail = {
        FAQItem.is_public: lambda m, a: fmt_bool(m.is_public),
        FAQItem.category: lambda m, a: (
            Markup(f'<span class="badge bg-blue-lt text-blue">{m.category}</span>')
            if m.category
            else "—"
        ),
    }
    column_details_list = [
        FAQItem.order_index,
        FAQItem.question,
        FAQItem.answer,
        FAQItem.category,
        FAQItem.is_public,
    ]
    column_default_sort = (FAQItem.order_index, False)

    form_widget_args = {
        FAQItem.question: {"placeholder": "Как добраться до старта?"},
        FAQItem.category: {"placeholder": "Транспорт / Безопасность / Проживание"},
    }

    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params
        if q.get("is_public") == "true":
            stmt = stmt.where(FAQItem.is_public.is_(True))
        elif q.get("is_public") == "false":
            stmt = stmt.where(FAQItem.is_public.is_(False))
        if cat := q.get("category"):
            stmt = stmt.where(FAQItem.category == cat)
        return stmt


class NewsPostAdmin(BaseAdminView, model=NewsPost):
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
        NewsPost.cover_url: "Обложка",
    }
    column_formatters = {
        NewsPost.published_at: lambda m, a: fmt_datetime(m.published_at),
        NewsPost.title: lambda m, a: Markup(
            f'<a href="/admin-panel/news-post/details/{m.id}" class="text-primary fw-bold text-decoration-none">{m.title}</a>'
        ),
        NewsPost.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number}</a>"
            )
            if m.stage
            else "—"
        ),
        NewsPost.is_important: lambda m, a: (
            Markup('<span class="badge bg-danger text-white">Важная</span>')
            if m.is_important
            else Markup('<span class="text-muted">—</span>')
        ),
        NewsPost.is_published: lambda m, a: (
            Markup('<span class="badge bg-success-lt text-success">Опубликована</span>')
            if m.is_published
            else Markup('<span class="badge bg-secondary-lt text-secondary">Черновик</span>')
        ),
        NewsPost.is_pinned: lambda m, a: fmt_bool(m.is_pinned),
        NewsPost.source: lambda m, a: fmt_news_source(m.source),
    }
    column_formatters_detail = {
        NewsPost.published_at: lambda m, a: fmt_datetime(m.published_at),
        NewsPost.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number} — {m.stage.name}</a>"
            )
            if m.stage
            else "—"
        ),
        NewsPost.is_important: lambda m, a: fmt_bool(m.is_important),
        NewsPost.is_published: lambda m, a: fmt_bool(m.is_published),
        NewsPost.is_pinned: lambda m, a: fmt_bool(m.is_pinned),
        NewsPost.source: lambda m, a: fmt_news_source(m.source),
        NewsPost.cover_url: lambda m, a: (
            Markup(
                f'<img src="{m.cover_url}" alt="{m.title}" '
                f'style="max-width:400px;border-radius:8px;border:1px solid var(--tblr-border-color);">'
            )
            if m.cover_url
            else Markup('<span class="text-muted">— обложка не загружена</span>')
        ),
        NewsPost.vk_url: lambda m, a: (
            Markup(
                f'<a href="{m.vk_url}" target="_blank" class="text-primary text-decoration-none">'
                f'Открыть пост ВК <i class="fa-solid fa-arrow-up-right-from-square ms-1 small"></i></a>'
            )
            if m.vk_url
            else "—"
        ),
    }
    column_details_list = [
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
    column_default_sort = (NewsPost.published_at, True)
    column_searchable_list = [NewsPost.title]
    column_selectinload = [NewsPost.stage]

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
        NewsPost.vk_url: {"placeholder": "https://vk.com/wall-..._..."},
    }
    form_overrides = {
        "source": SelectField,
        "cover_url": UploadImageField,
    }
    form_args = {
        "source": {
            "choices": [
                ("manual", "Вручную"),
                ("vk", "Из ВКонтакте"),
            ],
        },
    }

    # ═══ РУЧНАЯ ФИЛЬТРАЦИЯ ═══
    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if sid := get_int_param(request, "stage_id"):
            stmt = stmt.where(NewsPost.stage_id == sid)

        if q.get("is_published") == "true":
            stmt = stmt.where(NewsPost.is_published.is_(True))
        elif q.get("is_published") == "false":
            stmt = stmt.where(NewsPost.is_published.is_(False))

        if q.get("is_important") == "true":
            stmt = stmt.where(NewsPost.is_important.is_(True))
        elif q.get("is_important") == "false":
            stmt = stmt.where(NewsPost.is_important.is_(False))

        return stmt

    # ═══ ФИКС UploadFile → VARCHAR (как у участников) ═══
    async def update_model(self, request, pk, data):
        pk_int = int(pk)
        cover = data.get("cover_url")
        if cover is not None and hasattr(cover, "filename"):
            async with async_session_factory() as session:
                post = await session.get(NewsPost, pk_int)
                data["cover_url"] = post.cover_url if post is not None else None
        return await super().update_model(request, pk_int, data)

    async def create_model(self, request, data):
        cover = data.get("cover_url")
        if cover is not None and hasattr(cover, "filename"):
            data["cover_url"] = None
        return await super().create_model(request, data)

    # ═══ СОХРАНЕНИЕ ОБЛОЖКИ + УДАЛЕНИЕ СТАРОЙ ═══
    async def after_model_change(self, data, model, is_created, request):
        form = await request.form()
        upload = form.get("cover_url")

        if not upload or not hasattr(upload, "filename") or not upload.filename:
            await cache.invalidate_pattern("public:news:*")
            return

        old_url = None
        async with async_session_factory() as session:
            post = await session.get(NewsPost, model.id)
            if post is not None:
                old_url = post.cover_url

        try:
            new_url = await media_storage.save_image(
                upload,
                folder="news",
                prefix=f"news{model.id}",
            )
        except ValueError as e:
            print(f"[media] Ошибка загрузки обложки новости {model.id}: {e}")
            await cache.invalidate_pattern("public:news:*")
            return

        async with async_session_factory() as session:
            post = await session.get(NewsPost, model.id)
            if post is None:
                return
            post.cover_url = new_url
            await session.commit()

        if old_url and old_url != new_url and old_url.startswith("/media/"):
            media_storage.delete(old_url)

        await cache.invalidate_pattern("public:news:*")

    # --- BULK ACTIONS (без изменений) ---
    async def _set_published(
        self, request: Request, publish: bool, action_code: str
    ) -> RedirectResponse:
        pks = await self._parse_pks(request)
        if not pks:
            return RedirectResponse(
                request.url_for("admin:list", identity=self.identity),
                status_code=302,
            )

        session_id = request.session.get("admin_session_id")

        async with async_session_factory() as session:
            admin = await get_active_admin_for_session(session, str(session_id or ""))
            admin_id = admin.id if admin else None
            now = datetime.now(tz=UTC)

            for pk in pks:
                post = await session.get(NewsPost, pk)
                if post is None:
                    continue
                old_status = post.is_published
                post.is_published = publish
                if publish and post.published_at is None:
                    post.published_at = now
                session.add(
                    AuditLog(
                        admin_id=admin_id,
                        action=action_code,
                        entity_type="news_post",
                        entity_id=str(post.id),
                        payload={"old_status": old_status, "new_status": publish},
                    )
                )
            await session.commit()

        await cache.invalidate_pattern("public:news:*")
        await cache.invalidate_pattern("public:schedule:*")

        return RedirectResponse(
            request.url_for("admin:list", identity=self.identity),
            status_code=302,
        )

    @action(
        name="publish",
        label="Опубликовать",
        confirmation_message="Опубликовать выбранные новости?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_publish(self, request: Request) -> RedirectResponse:
        return await self._set_published(request, True, "news_published")

    @action(
        name="unpublish",
        label="Снять с публикации",
        confirmation_message="Снять выбранные новости с публикации?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_unpublish(self, request: Request) -> RedirectResponse:
        return await self._set_published(request, False, "news_unpublished")

    @action(
        name="mark-important",
        label="Пометить важной",
        confirmation_message="Пометить выбранные новости как важные?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_mark_important(self, request: Request) -> RedirectResponse:
        pks = await self._parse_pks(request)
        if not pks:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), 302)

        session_id = request.session.get("admin_session_id")
        async with async_session_factory() as session:
            admin = await get_active_admin_for_session(session, str(session_id or ""))
            admin_id = admin.id if admin else None

            for pk in pks:
                post = await session.get(NewsPost, pk)
                if post is None:
                    continue
                post.is_important = True
                session.add(
                    AuditLog(
                        admin_id=admin_id,
                        action="news_marked_important",
                        entity_type="news_post",
                        entity_id=str(post.id),
                        payload={"is_important": True},
                    )
                )
            await session.commit()

        await cache.invalidate_pattern("public:news:*")
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), 302)


class ScheduleEventAdmin(BaseAdminView, model=ScheduleEvent):
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
        ScheduleEvent.title: lambda m, a: Markup(
            f'<a href="/admin-panel/schedule-event/details/{m.id}" class="text-primary fw-bold text-decoration-none">{m.title}</a>'
        ),
        ScheduleEvent.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number}</a>"
            )
            if m.stage
            else "—"
        ),
        ScheduleEvent.is_public: lambda m, a: fmt_bool(m.is_public),
        ScheduleEvent.kind: lambda m, a: fmt_schedule_kind(m.kind),
    }
    column_formatters_detail = {
        ScheduleEvent.starts_at: lambda m, a: fmt_datetime(m.starts_at),
        ScheduleEvent.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number} — {m.stage.name}</a>"
            )
            if m.stage
            else "—"
        ),
        ScheduleEvent.is_public: lambda m, a: fmt_bool(m.is_public),
        ScheduleEvent.kind: lambda m, a: fmt_schedule_kind(m.kind),
    }
    column_details_list = [
        ScheduleEvent.starts_at,
        ScheduleEvent.title,
        ScheduleEvent.description,
        ScheduleEvent.kind,
        ScheduleEvent.stage,
        ScheduleEvent.location,
        ScheduleEvent.is_public,
    ]
    column_default_sort = (ScheduleEvent.starts_at, False)
    column_searchable_list = [ScheduleEvent.title]
    column_selectinload = [ScheduleEvent.stage]

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

    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if sid := get_int_param(request, "stage_id"):
            stmt = stmt.where(ScheduleEvent.stage_id == sid)

        if kind := q.get("kind"):
            stmt = stmt.where(ScheduleEvent.kind == kind)

        if q.get("is_public") == "true":
            stmt = stmt.where(ScheduleEvent.is_public.is_(True))
        elif q.get("is_public") == "false":
            stmt = stmt.where(ScheduleEvent.is_public.is_(False))

        return stmt


class ViewerLocationAdmin(BaseAdminView, model=ViewerLocation):
    name = "Зрительская локация"
    name_plural = "Зрительские локации"
    icon = "fa-solid fa-map-location-dot"
    category = CategoryAdminEnum.CATEGORY_CONTENT
    category_icon = "fa-solid fa-newspaper"

    column_list = [
        ViewerLocation.name,
        ViewerLocation.kind,
        ViewerLocation.category,
        ViewerLocation.glyph,
        ViewerLocation.travel_time_minutes,
        ViewerLocation.stage,
        ViewerLocation.is_public,
    ]
    column_labels = {
        ViewerLocation.name: "Название",
        ViewerLocation.kind: "Тип",
        ViewerLocation.category: "Категория",
        ViewerLocation.glyph: "Иконка",
        ViewerLocation.travel_time_minutes: "В пути, мин",
        ViewerLocation.stage: "Этап",
        ViewerLocation.is_public: "Публичная",
    }
    column_formatters = {
        ViewerLocation.name: lambda m, a: Markup(
            f'<a href="/admin-panel/viewer-location/details/{m.id}" class="text-primary fw-bold text-decoration-none">{m.name}</a>'
        ),
        ViewerLocation.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number}</a>"
            )
            if m.stage
            else "—"
        ),
        ViewerLocation.is_public: lambda m, a: fmt_bool(m.is_public),
        ViewerLocation.kind: lambda m, a: fmt_viewer_kind(m.kind),
    }
    column_formatters_detail = {
        ViewerLocation.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number} — {m.stage.name}</a>"
            )
            if m.stage
            else "—"
        ),
        ViewerLocation.is_public: lambda m, a: fmt_bool(m.is_public),
        ViewerLocation.kind: lambda m, a: fmt_viewer_kind(m.kind),
        ViewerLocation.lat: lambda m, a: (
            Markup(
                f'<a href="https://yandex.ru/maps/?pt={m.lon},{m.lat}&z=13&l=map" target="_blank" class="text-primary text-decoration-none">'
                f'{m.lat:.5f} <i class="fa-solid fa-arrow-up-right-from-square ms-1 small"></i></a>'
            )
            if m.lat is not None
            else "—"
        ),
        ViewerLocation.lon: lambda m, a: (
            Markup(
                f'<a href="https://yandex.ru/maps/?pt={m.lon},{m.lat}&z=13&l=map" target="_blank" class="text-primary text-decoration-none">'
                f'{m.lon:.5f} <i class="fa-solid fa-arrow-up-right-from-square ms-1 small"></i></a>'
            )
            if m.lon is not None
            else "—"
        ),
    }
    column_details_list = [
        ViewerLocation.name,
        ViewerLocation.kind,
        ViewerLocation.category,
        ViewerLocation.glyph,
        ViewerLocation.description,
        ViewerLocation.travel_time_minutes,
        ViewerLocation.lat,
        ViewerLocation.lon,
        ViewerLocation.stage,
        ViewerLocation.is_public,
    ]
    column_searchable_list = [ViewerLocation.name]
    column_selectinload = [ViewerLocation.stage]

    form_overrides = {
        "kind": SelectField,
        "category": SelectField,
        "glyph": SelectField,
    }
    form_args = {
        "category": {
            "label": "Категория",
            "choices": [
                (category.value, label)
                for category, label in zip(
                    ViewerLocationCategory,
                    ("Сцены", "Площадки", "Еда", "Детям", "Другое"),
                    strict=True,
                )
            ],
        },
        "kind": {
            "choices": [
                ("start", "Старт"),
                ("finish", "Финиш"),
                ("viewpoint", "Смотровая"),
                ("festival", "Фестиваль"),
                ("other", "Другое"),
            ],
        },
        "glyph": {
            "choices": [
                ("mic", "Сцена (микрофон)"),
                ("food", "Еда"),
                ("house", "Шатёр (домик)"),
                ("image", "Фотозона"),
                ("globe", "Этнозона (глобус)"),
                ("smile", "Детская зона"),
                ("pin", "Дефолт (пин)"),
            ],
        },
    }

    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if sid := get_int_param(request, "stage_id"):
            stmt = stmt.where(ViewerLocation.stage_id == sid)

        if kind := q.get("kind"):
            stmt = stmt.where(ViewerLocation.kind == kind)

        if q.get("is_public") == "true":
            stmt = stmt.where(ViewerLocation.is_public.is_(True))
        elif q.get("is_public") == "false":
            stmt = stmt.where(ViewerLocation.is_public.is_(False))

        return stmt

    async def after_model_change(self, data, model, is_created, request):
        await cache.invalidate_pattern("public:viewer-locations:*")
