import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UserRepoDep, get_current_user
from app.config import get_settings
from app.db.base import get_session
from app.db.models.user import User
from app.schemas.public import AuthResponse, UserProfile, VKAuthRequest
from app.security.tokens import create_user_token
from app.security.vk_auth import verify_vk_launch_params

logger = logging.getLogger("avacha.auth")

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/vk", response_model=AuthResponse)
async def auth_vk(
        body: VKAuthRequest,
        users: UserRepoDep,
        session: AsyncSession = Depends(get_session),
):
    params = body.params

    if not verify_vk_launch_params(params, settings.VK_SECURE_KEY):
        logger.warning(
            "vk_signature_invalid",
            extra={
                "vk_user_id": params.get("vk_user_id"),
                "vk_platform": params.get("vk_platform"),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid VK signature",
        )

    try:
        vk_user_id = int(params["vk_user_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing vk_user_id",
        ) from None

    # User info приходит с фронта (VK Bridge: VKWebAppGetUserInfo)
    first_name = ""
    last_name = ""
    photo_url = None
    if body.user_info is not None:
        first_name = body.user_info.first_name
        last_name = body.user_info.last_name
        photo_url = body.user_info.photo_200

    platform = params.get("vk_platform")
    notifications_param = params.get("vk_are_notifications_enabled")

    # --- Работа с БД через репозиторий ---
    user = await users.get_by_vk_user_id(vk_user_id)
    is_new_user = user is None

    # Парсим параметр уведомлений заранее
    if notifications_param is not None:
        notifications_allowed: bool | None = notifications_param == "1"
    else:
        notifications_allowed = None

    if user is None:
        user = await users.create(
            vk_user_id=vk_user_id,
            first_name=first_name,
            last_name=last_name,
            photo_url=photo_url,
            platform=platform,
            notifications_allowed=notifications_allowed or False,
        )
    else:
        user = await users.update_from_vk(
            user,
            first_name=first_name,
            last_name=last_name,
            photo_url=photo_url,
            platform=platform,
            notifications_allowed=notifications_allowed,
        )
        await users.touch_last_seen(user)

    await session.commit()

    token, expires_in = create_user_token(user.id, user.vk_user_id)
    return AuthResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserProfile.model_validate(user),
        is_new_user=is_new_user,
    )


@router.get("/me", response_model=UserProfile)
async def me(user: User = Depends(get_current_user)):
    return user
