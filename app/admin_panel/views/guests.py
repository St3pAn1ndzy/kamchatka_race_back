"""Админка для раздела «Гостям»."""

import logging

from markupsafe import Markup
from wtforms import SelectField

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool
from app.admin_panel.views.participants import UploadImageField
from app.db.base import async_session_factory
from app.db.models.guest_item import GuestItem
from app.enums import GuestItemSection
from app.services.cache import cache
from app.services.media_storage import media_storage

logger = logging.getLogger(__name__)

SECTION_LABELS = {
    GuestItemSection.CLOTHING.value: "Одежда",
    GuestItemSection.SHOES.value: "Обувь",
    GuestItemSection.EQUIPMENT.value: "Снаряжение",
}


class GuestItemAdmin(BaseAdminView, model=GuestItem):
    name = "Элемент «Что взять с собой»"
    name_plural = "Что взять с собой"
    icon = "fa-solid fa-suitcase"
    category = CategoryAdminEnum.CATEGORY_CONTENT
    category_icon = "fa-solid fa-newspaper"

    column_list = [
        GuestItem.section,
        GuestItem.order_index,
        GuestItem.title,
        GuestItem.image_url,
        GuestItem.is_public,
    ]
    column_labels = {
        GuestItem.section: "Раздел",
        GuestItem.order_index: "Порядок",
        GuestItem.title: "Заголовок",
        GuestItem.image_url: "Фото",
        GuestItem.is_public: "Публичный",
    }
    column_formatters = {
        GuestItem.section: lambda m, a: Markup(
            f'<span class="badge bg-blue-lt text-blue">{SECTION_LABELS.get(m.section, m.section)}</span>'
        ),
        GuestItem.is_public: lambda m, a: fmt_bool(m.is_public),
        GuestItem.title: lambda m, a: Markup(
            f'<a href="/admin-panel/guest-item/details/{m.id}" class="text-primary fw-bold text-decoration-none">{m.title}</a>'
        ),
    }
    column_formatters_detail = {
        GuestItem.section: lambda m, a: Markup(
            f'<span class="badge bg-blue-lt text-blue">{SECTION_LABELS.get(m.section, m.section)}</span>'
        ),
        GuestItem.is_public: lambda m, a: fmt_bool(m.is_public),
        GuestItem.image_url: lambda m, a: (
            Markup(f'<img src="{m.image_url}" style="max-width:200px;border-radius:6px;">')
            if m.image_url
            else Markup('<span class="text-muted">—</span>')
        ),
    }
    column_details_list = [
        GuestItem.section,
        GuestItem.title,
        GuestItem.text,
        GuestItem.image_url,
        GuestItem.order_index,
        GuestItem.is_public,
    ]
    column_searchable_list = [GuestItem.title]
    column_default_sort = (GuestItem.section, False)

    form_columns = [
        GuestItem.section,
        GuestItem.title,
        GuestItem.text,
        GuestItem.image_url,
        GuestItem.order_index,
        GuestItem.is_public,
    ]
    form_overrides = {
        "section": SelectField,
        "image_url": UploadImageField,
    }
    form_args = {
        "section": {
            "choices": [(s.value, SECTION_LABELS[s.value]) for s in GuestItemSection],
        },
    }
    form_widget_args = {
        GuestItem.title: {"placeholder": "Первый слой"},
        GuestItem.text: {"placeholder": "Качественное термобелье..."},
        GuestItem.order_index: {"placeholder": "0"},
    }

    async def update_model(self, request, pk, data):
        pk_int = int(pk)
        img = data.get("image_url")
        if img is not None and hasattr(img, "filename"):
            async with async_session_factory() as session:
                item = await session.get(GuestItem, pk_int)
                data["image_url"] = item.image_url if item else None
        return await super().update_model(request, pk_int, data)

    async def create_model(self, request, data):
        img = data.get("image_url")
        if img is not None and hasattr(img, "filename"):
            data["image_url"] = None
        return await super().create_model(request, data)

    async def after_model_change(self, data, model, is_created, request):
        form = await request.form()
        upload = form.get("image_url")

        if upload and hasattr(upload, "filename") and upload.filename:
            old_url = None
            async with async_session_factory() as session:
                item = await session.get(GuestItem, model.id)
                if item is not None:
                    old_url = item.image_url

            try:
                new_url = await media_storage.save_image(
                    upload, folder="guests", prefix=f"guest{model.id}"
                )
            except ValueError as e:
                logger.warning("Ошибка загрузки фото GuestItem %s: %s", model.id, e)
            else:
                async with async_session_factory() as session:
                    item = await session.get(GuestItem, model.id)
                    if item is not None:
                        item.image_url = new_url
                        await session.commit()
                if old_url and old_url != new_url and old_url.startswith("/media/"):
                    media_storage.delete(old_url)

        await cache.invalidate_pattern("public:guests:*")

    async def after_model_delete(self, model, request):
        await cache.invalidate_pattern("public:guests:*")
        await super().after_model_delete(model, request)
