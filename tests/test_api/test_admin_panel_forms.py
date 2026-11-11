"""Регрессии настоящих HTTP-форм SQLAdmin на тестовой базе"""

import re

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqladmin import Admin
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from app.admin_panel.views.content import ViewerLocationAdmin
from app.admin_panel.views.results import OfficialMarkAdmin
from app.admin_panel.views.system import AdminAccountAdmin
from app.db.models import AdminAccount, AuditLog, OfficialMark, Participant, ViewerLocation
from app.enums import ViewerLocationCategory
from app.security.passwords import verify_password
from app.services.cache import cache


@pytest.fixture
async def forms_client(db_session, create_admin, monkeypatch):
    await cache.close()
    admin = await create_admin(login="forms-judge")

    class FormAuth(AuthenticationBackend):
        async def authenticate(self, request):
            if request.headers.get("x-test-admin") != "authenticated":
                return False
            request.state.admin_id = admin.id
            return True

    class MarkView(OfficialMarkAdmin):
        pass

    class AccountView(AdminAccountAdmin):
        pass

    class LocationView(ViewerLocationAdmin):
        pass

    application = FastAPI()
    session_factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr("app.admin_panel.views.results.async_session_factory", session_factory)
    panel = Admin(
        application,
        session_maker=session_factory,
        base_url="/admin-panel",
        authentication_backend=FormAuth(secret_key="test-forms"),
    )
    for view in (MarkView, AccountView, LocationView):
        panel.add_view(view)
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
        headers={"x-test-admin": "authenticated"},
    ) as client:
        yield client, admin.id
    await cache.close()


def account_data(**overrides):
    return {
        "login": "new-admin",
        "display_name": "Новый администратор",
        "vk_user_id": "",
        "is_active": "y",
        "password": "Надёжный пароль",
        **overrides,
    }


def location_data(**overrides):
    return {
        "name": "Площадка",
        "kind": "viewpoint",
        "category": "food",
        "lat": "53",
        "lon": "158",
        "safety_notes": "Соблюдайте правила",
        **overrides,
    }


async def test_account_create_password_is_hashed(forms_client, db_session):
    """Создание администратора сохраняет хеш пароля, подходящий для входа"""
    client, _ = forms_client
    response = await client.post("/admin-panel/admin-account/create", data=account_data())
    assert response.status_code == 302, response.text
    account = await db_session.scalar(select(AdminAccount).where(AdminAccount.login == "new-admin"))
    assert verify_password("Надёжный пароль", account.password_hash)


async def test_account_password_is_write_only_and_blank_edit_preserves_hash(
    forms_client, db_session, create_admin
):
    """Форма не раскрывает пароль или хеш, пустое поле при редактировании сохраняет пароль"""
    client, _ = forms_client
    account = await create_admin(login="editable")
    original_hash = account.password_hash
    page = await client.get(f"/admin-panel/admin-account/edit/{account.id}")
    assert page.status_code == 200
    assert re.search(r'<input[^>]*name="password"[^>]*type="password"', page.text)
    assert original_hash not in page.text
    assert "password_hash" not in page.text
    response = await client.post(
        f"/admin-panel/admin-account/edit/{account.id}",
        data=account_data(login="editable", password=""),
    )
    assert response.status_code == 302, response.text
    await db_session.refresh(account)
    assert account.password_hash == original_hash


@pytest.mark.parametrize("password", ["x" * 73, "я" * 37])
async def test_account_rejects_password_over_72_utf8_bytes(forms_client, db_session, password):
    """Слишком длинный пароль отклоняется до записи и не возвращается в HTML"""
    client, _ = forms_client
    response = await client.post(
        "/admin-panel/admin-account/create", data=account_data(password=password)
    )
    assert response.status_code == 400
    assert "72 байт" in response.text
    assert password not in response.text
    assert (
        await db_session.scalar(select(AdminAccount).where(AdminAccount.login == "new-admin"))
        is None
    )


async def test_account_requires_password_for_login(forms_client):
    """Создание администратора с логином требует пароль и показывает понятную ошибку"""
    client, _ = forms_client
    response = await client.post(
        "/admin-panel/admin-account/create", data=account_data(password="")
    )
    assert response.status_code == 400
    assert "Для входа по логину укажите пароль" in response.text
    assert "INSERT INTO" not in response.text


@pytest.mark.parametrize("password", ["x" * 72, "я" * 36])
async def test_account_accepts_exactly_72_utf8_bytes(forms_client, db_session, password):
    """Пароль на границе ограничения bcrypt сохраняется без усечения"""
    client, _ = forms_client
    response = await client.post(
        "/admin-panel/admin-account/create", data=account_data(password=password)
    )
    assert response.status_code == 302, response.text
    account = await db_session.scalar(select(AdminAccount).where(AdminAccount.login == "new-admin"))
    assert verify_password(password, account.password_hash)


async def test_account_edit_replaces_password_and_never_renders_it(
    forms_client, db_session, create_admin
):
    """Новый пароль заменяет прежний и не появляется в ответе формы"""
    client, _ = forms_client
    account = await create_admin(login="editable")
    old_hash = account.password_hash
    response = await client.post(
        f"/admin-panel/admin-account/edit/{account.id}",
        data=account_data(login="editable"),
    )
    assert response.status_code == 302, response.text
    await db_session.refresh(account)
    assert account.password_hash != old_hash
    assert verify_password("Надёжный пароль", account.password_hash)
    page = await client.get(f"/admin-panel/admin-account/edit/{account.id}")
    assert "Надёжный пароль" not in page.text
    assert account.password_hash not in page.text
    assert not re.search(r'<input[^>]*name="password"[^>]*value="[^"]+"', page.text)


async def test_account_invalid_password_edit_preserves_hash(forms_client, db_session, create_admin):
    """Ошибка проверки нового пароля не меняет прежний хеш"""
    client, _ = forms_client
    account = await create_admin(login="editable")
    old_hash = account.password_hash
    response = await client.post(
        f"/admin-panel/admin-account/edit/{account.id}",
        data=account_data(login="editable", password="я" * 37),
    )
    assert response.status_code == 400
    assert "72 байт" in response.text
    assert "я" * 37 not in response.text
    await db_session.refresh(account)
    assert account.password_hash == old_hash


async def test_vk_account_can_be_created_without_password_and_requires_it_for_login(
    forms_client, db_session
):
    """Учётная запись ВК допускает отсутствие пароля, добавление логина требует его задать"""
    client, _ = forms_client
    response = await client.post(
        "/admin-panel/admin-account/create",
        data=account_data(login="", vk_user_id="987654", password=""),
    )
    assert response.status_code == 302, response.text
    account = await db_session.scalar(select(AdminAccount).where(AdminAccount.vk_user_id == 987654))
    response = await client.post(
        f"/admin-panel/admin-account/edit/{account.id}",
        data=account_data(vk_user_id="987654", password=""),
    )
    assert response.status_code == 400
    assert "Для входа по логину укажите пароль" in response.text
    await db_session.refresh(account)
    assert account.login is None
    response = await client.post(
        f"/admin-panel/admin-account/edit/{account.id}",
        data=account_data(vk_user_id="987654"),
    )
    assert response.status_code == 302, response.text
    await db_session.refresh(account)
    assert verify_password("Надёжный пароль", account.password_hash)


async def test_location_category_is_enum_select(forms_client):
    """Форма предлагает только категории, поддерживаемые публичным API"""
    client, _ = forms_client
    page = await client.get("/admin-panel/viewer-location/create")
    assert page.status_code == 200
    field = re.search(r'<select[^>]*name="category"[^>]*>(.*?)</select>', page.text, re.S)
    assert field is not None
    assert set(re.findall(r'<option[^>]*value="([^"]+)"', field[1])) == {
        category.value for category in ViewerLocationCategory
    }


@pytest.mark.parametrize("category", ["food", "forged", ""])
async def test_location_category_is_validated_on_create(forms_client, db_session, category):
    """Допустимая категория сохраняется, поддельная или пустая отклоняется"""
    client, _ = forms_client
    response = await client.post(
        "/admin-panel/viewer-location/create", data=location_data(category=category)
    )
    assert response.status_code == (302 if category == "food" else 400), response.text
    location = await db_session.scalar(select(ViewerLocation))
    if category == "food":
        assert location.category == "food"
    else:
        assert location is None


async def test_location_invalid_edit_leaves_persisted_category_untouched(
    forms_client, db_session, create_viewer_location
):
    """Некорректное редактирование категории не меняет запись в базе"""
    client, _ = forms_client
    location = await create_viewer_location()
    location.category = "legacy-invalid"
    await db_session.flush()
    response = await client.post(
        f"/admin-panel/viewer-location/edit/{location.id}",
        data=location_data(category="legacy-invalid"),
    )
    assert response.status_code == 400
    await db_session.refresh(location)
    assert location.category == "legacy-invalid"


@pytest.fixture
async def mark_form(create_season, create_stage, create_checkpoint, create_participant):
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    checkpoint = await create_checkpoint(stage_id=stage.id)
    participant = await create_participant()
    return stage, {
        "participant": str(participant.id),
        "checkpoint": str(checkpoint.id),
        "mark_time": "2027-03-01 03:00:00",
        "penalty_minutes": "5",
        "mandatory_stop_minutes": "2",
        "comment": "Судейская отметка",
        "entered_by_admin_id": "999999",
    }


async def test_mark_creation_assigns_author_audits_and_invalidates_cache(
    forms_client, db_session, mark_form
):
    """Отметка получает текущего автора, аудит и сброс кеша, повторная отметка отклоняется"""
    client, admin_id = forms_client
    stage, data = mark_form
    keys = [
        f"public:results:stage:{stage.id}",
        "public:results:standings",
        "public:results:leaderboard:test",
    ]
    for key in keys:
        await cache.set(key, {"stale": True}, ttl=60)
        assert await cache.get(key) == {"stale": True}
    response = await client.post("/admin-panel/official-mark/create", data=data)
    assert response.status_code == 302, response.text
    mark = await db_session.scalar(select(OfficialMark))
    assert mark.entered_by_admin_id == admin_id
    assert mark.penalty_minutes == 5
    assert mark.mark_time.utcoffset().total_seconds() == 0
    log = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "official_mark_created")
    )
    assert log.admin_id == admin_id
    assert log.entity_id == str(mark.id)
    for key in keys:
        assert await cache.get(key) is None
    duplicate = await client.post("/admin-panel/official-mark/create", data=data)
    assert duplicate.status_code == 400
    assert "Действующая отметка уже существует" in duplicate.text
    assert await db_session.scalar(select(func.count()).select_from(OfficialMark)) == 1
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == 1


async def test_mark_rejects_cross_season_without_mark_or_audit(
    forms_client, db_session, mark_form, create_season, create_discipline
):
    """Отметка между разными сезонами отклоняется без записи данных и аудита"""
    client, _ = forms_client
    _, data = mark_form
    season = await create_season(year=2028)
    discipline = await create_discipline(season_id=season.id)
    participant = await db_session.get(Participant, int(data["participant"]))
    participant.discipline_id = discipline.id
    await db_session.flush()
    response = await client.post("/admin-panel/official-mark/create", data=data)
    assert response.status_code == 400
    assert "Участник и КП относятся к разным сезонам" in response.text
    assert await db_session.scalar(select(func.count()).select_from(OfficialMark)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == 0


async def test_mark_audit_failure_rolls_back_mark_and_preserves_cache(
    forms_client, db_session, mark_form
):
    """Ошибка сохранения аудита откатывает отметку и оставляет кеш нетронутым"""
    client, _ = forms_client
    stage, data = mark_form
    key = f"public:results:stage:{stage.id}"
    await cache.set(key, {"stale": True}, ttl=60)
    assert await cache.get(key) == {"stale": True}

    def reject_audit(session, flush_context, instances):
        if any(isinstance(obj, AuditLog) for obj in session.new):
            raise ValueError("Тестовая ошибка сохранения аудита")

    event.listen(Session, "before_flush", reject_audit)
    try:
        response = await client.post("/admin-panel/official-mark/create", data=data)
    finally:
        event.remove(Session, "before_flush", reject_audit)
    assert response.status_code == 400
    assert "Тестовая ошибка сохранения аудита" in response.text
    assert await db_session.scalar(select(func.count()).select_from(OfficialMark)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == 0
    assert await cache.get(key) == {"stale": True}


async def test_mark_form_requires_authentication(forms_client, mark_form):
    """Создание отметки без входа перенаправляет на авторизацию"""
    client, _ = forms_client
    _, data = mark_form
    client.headers.pop("x-test-admin")
    response = await client.post("/admin-panel/official-mark/create", data=data)
    assert response.status_code == 302
    assert response.headers["location"].endswith("/admin-panel/login")
