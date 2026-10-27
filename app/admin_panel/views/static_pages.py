from markupsafe import Markup

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime
from app.admin_panel.views.participants import UploadImageField
from app.db.base import async_session_factory
from app.db.models.static_page import StaticPage
from app.services.cache import cache
from app.services.media_storage import media_storage


class StaticPageAdmin(BaseAdminView, model=StaticPage):
    name = "Статичная страница"
    name_plural = "Статичные страницы"
    icon = "fa-solid fa-file-lines"
    category = CategoryAdminEnum.CATEGORY_CONTENT
    category_icon = "fa-solid fa-newspaper"

    column_list = [
        StaticPage.slug,
        StaticPage.title,
        StaticPage.is_published,
        StaticPage.updated_at,
    ]
    column_labels = {
        StaticPage.slug: "Ключ (slug)",
        StaticPage.title: "Заголовок",
        StaticPage.is_published: "Опубликована",
        StaticPage.updated_at: "Обновлена",
    }
    column_formatters = {
        StaticPage.slug: lambda m, a: Markup(
            f'<a href="/admin-panel/static-page/details/{m.id}" class="text-primary fw-bold text-decoration-none"><code>{m.slug}</code></a>'
        ),
        StaticPage.is_published: lambda m, a: fmt_bool(m.is_published),
        StaticPage.updated_at: lambda m, a: fmt_datetime(m.updated_at),
    }
    column_formatters_detail = {
        StaticPage.is_published: lambda m, a: fmt_bool(m.is_published),
        StaticPage.created_at: lambda m, a: fmt_datetime(m.created_at),
        StaticPage.updated_at: lambda m, a: fmt_datetime(m.updated_at),
        StaticPage.cover_url: lambda m, a: (
            Markup(f'<img src="{m.cover_url}" style="max-width:400px;border-radius:8px;">')
            if m.cover_url
            else Markup('<span class="text-muted">—</span>')
        ),
    }
    column_details_list = [
        StaticPage.slug,
        StaticPage.title,
        StaticPage.content,
        StaticPage.cover_url,
        StaticPage.is_published,
        StaticPage.created_at,
        StaticPage.updated_at,
    ]
    column_searchable_list = [StaticPage.slug, StaticPage.title]

    form_columns = [
        StaticPage.slug,
        StaticPage.title,
        StaticPage.content,
        StaticPage.cover_url,
        StaticPage.is_published,
    ]
    form_overrides = {
        "cover_url": UploadImageField,
    }
    form_widget_args = {
        StaticPage.slug: {"placeholder": "about / rules / organizers"},
        StaticPage.title: {"placeholder": "О гонке «Авача»"},
        StaticPage.content: {
            "rows": 20,
            "placeholder": "Текст в Markdown. Картинки вставляются как ![alt](/media/pages/img.jpg)",
        },
    }

    # Фикс загрузки обложки (как у новостей/участников)
    async def update_model(self, request, pk, data):
        pk_int = int(pk)
        cover = data.get("cover_url")
        if cover is not None and hasattr(cover, "filename"):
            async with async_session_factory() as session:
                page = await session.get(StaticPage, pk_int)
                data["cover_url"] = page.cover_url if page else None
        return await super().update_model(request, pk_int, data)

    async def create_model(self, request, data):
        cover = data.get("cover_url")
        if cover is not None and hasattr(cover, "filename"):
            data["cover_url"] = None
        return await super().create_model(request, data)

    async def after_model_change(self, data, model, is_created, request):
        # Существующая логика загрузки обложки
        form = await request.form()
        upload = form.get("cover_url")

        if upload and hasattr(upload, "filename") and upload.filename:
            old_url = None
            async with async_session_factory() as session:
                page = await session.get(StaticPage, model.id)
                if page is not None:
                    old_url = page.cover_url

            try:
                new_url = await media_storage.save_image(
                    upload, folder="pages", prefix=f"page{model.id}"
                )
            except ValueError as e:
                print(f"[media] Ошибка загрузки обложки страницы {model.id}: {e}")
                await cache.invalidate_pattern("public:pages:*")
                return

            async with async_session_factory() as session:
                page = await session.get(StaticPage, model.id)
                if page is None:
                    return
                page.cover_url = new_url
                await session.commit()

            if old_url and old_url != new_url and old_url.startswith("/media/"):
                media_storage.delete(old_url)

        await cache.invalidate_pattern("public:pages:*")

    async def after_model_delete(self, model, request):
        await cache.invalidate_pattern("public:pages:*")
        await super().after_model_delete(model, request)
