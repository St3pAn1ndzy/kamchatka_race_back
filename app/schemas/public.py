from pydantic import Field

from app.schemas.base import BaseSchema

# --- Auth ---


class VKUserInfo(BaseSchema):
    """Имя и фото из VKWebAppGetUserInfo (VK Bridge)."""

    first_name: str = ""
    last_name: str = ""
    photo_200: str | None = None


class VKAuthRequest(BaseSchema):
    """Запрос на вход через VK ID.

    `params` — все launch_params от VK Bridge, включая sign.
    `user_info` — имя/фото из VKWebAppGetUserInfo (VK Bridge).
    """

    params: dict = Field(..., description="Все launch_params VK, включая sign")
    user_info: VKUserInfo | None = Field(
        None,
        description="Имя и фото из VKWebAppGetUserInfo",
    )


class UserProfile(BaseSchema):
    """Профиль пользователя в ответе API."""

    id: int
    vk_user_id: int
    first_name: str
    last_name: str
    photo_url: str | None = None
    notifications_allowed: bool


class AuthResponse(BaseSchema):
    """Ответ на успешный вход через VK ID."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile
    is_new_user: bool
