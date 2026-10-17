# Тесты admin_sessions:
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import AuditLog
from app.security.admin_sessions import (
    authenticate_admin_by_password,
    create_admin_session,
    get_active_admin_for_session,
    revoke_admin_session,
)


async def test_authenticate_admin_ok(db_session, create_admin) -> None:
    login = "admin"
    password = "admin123"

    admin = await create_admin(login=login, password=password)
    admin_id = admin.id

    result = await authenticate_admin_by_password(db_session, login, password)

    assert result is not None
    assert result.id == admin_id


async def test_authenticate_not_found(db_session) -> None:
    assert await authenticate_admin_by_password(db_session, "nobody", "x") is None


async def test_authenticate_wrong_password(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="correct")  # noqa F841
    assert await authenticate_admin_by_password(db_session, "admin", "wrong") is None


async def test_authenticate_inactive(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="x", is_active=False)  # noqa F841
    assert await authenticate_admin_by_password(db_session, "admin", "x") is None


async def test_create_admin_session_ok(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    admin_id = admin.id

    result = await create_admin_session(db_session, admin, surface="test")

    assert result is not None
    assert result.admin_id == admin_id
    assert result.expires_at > datetime.now(tz=UTC)


async def test_create_admin_session_writes_audit_log(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    admin_id = admin.id

    result = await create_admin_session(db_session, admin, surface="test")

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "admin_login",
                AuditLog.entity_id == str(result.id),
            )
        )
    ).scalar_one()

    assert audit.admin_id == admin_id
    assert audit.payload["surface"] == "test"


async def test_create_admin_session_unique_ids(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    s1 = await create_admin_session(db_session, admin, surface="test")
    s2 = await create_admin_session(db_session, admin, surface="test")
    assert s1.session_id != s2.session_id


async def test_get_active_admin_for_session_ok(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    admin_id = admin.id

    admin_session = await create_admin_session(db_session, admin, surface="test")

    result = await get_active_admin_for_session(
        db_session,
        session_id=admin_session.session_id,
        admin_id=admin_id,
    )

    assert result is not None
    assert result.id == admin_id


async def test_get_active_session_not_found(db_session) -> None:
    result = await get_active_admin_for_session(db_session, session_id="")
    assert result is None


async def test_get_active_session_revoked(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    admin_session = await create_admin_session(db_session, admin, surface="test")

    admin_session.revoked_at = datetime.now(tz=UTC)
    await db_session.flush()

    result = await get_active_admin_for_session(db_session, session_id=admin_session.session_id)
    assert result is None


async def test_get_active_session_expired(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    admin_session = await create_admin_session(db_session, admin, surface="test")

    admin_session.expires_at = datetime.now(tz=UTC) - timedelta(days=1)
    await db_session.flush()

    result = await get_active_admin_for_session(db_session, session_id=admin_session.session_id)
    assert result is None


async def test_get_active_session_admin_id_mismatch(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    other_admin = await create_admin(login="other", password="x")

    admin_session = await create_admin_session(db_session, admin, surface="test")

    result = await get_active_admin_for_session(
        db_session,
        session_id=admin_session.session_id,
        admin_id=other_admin.id,
    )

    assert result is None


async def test_get_active_session_admin_inactive(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    admin_session = await create_admin_session(db_session, admin, surface="test")

    admin.is_active = False
    await db_session.flush()

    result = await get_active_admin_for_session(db_session, session_id=admin_session.session_id)
    assert result is None


async def test_revoke_admin_session_ok(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    admin_session = await create_admin_session(db_session, admin, surface="test")
    session_id = admin_session.session_id

    result = await revoke_admin_session(db_session, session_id=session_id, surface="test")

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "admin_logout",
                AuditLog.entity_id == str(admin_session.id),
            )
        )
    ).scalar_one()

    assert result is not None
    assert result.session_id == session_id
    assert result.revoked_at is not None

    assert audit.admin_id == admin.id
    assert audit.payload["surface"] == "test"


async def test_revoke_admin_session_not_found(db_session) -> None:
    result = await revoke_admin_session(
        db_session, session_id="nonexistent-session-id", surface="test"
    )
    assert result is None


async def test_revoke_admin_session_idempotent(db_session, create_admin) -> None:
    admin = await create_admin(login="admin", password="admin123")
    admin_session = await create_admin_session(db_session, admin, surface="test")
    session_id = admin_session.session_id

    first = await revoke_admin_session(db_session, session_id=session_id, surface="test")
    first_revoked_at = first.revoked_at

    second = await revoke_admin_session(db_session, session_id=session_id, surface="test")

    assert second is not None
    assert second.revoked_at == first_revoked_at

    audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "admin_logout",
                    AuditLog.entity_id == str(admin_session.id),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
