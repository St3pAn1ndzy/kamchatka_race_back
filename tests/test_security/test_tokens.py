# Тесты tokens: проверяется корректное
# создание токенов для пользователя и админа,
# а также тестирование правильности декодирования

import base64
import json

from app.security.tokens import (
    create_admin_token,
    create_user_token,
    decode_token,
)

USER_ID = 1
VK_USER_ID = 192837465

ADMIN_ID = 1
SESSION_ID = "0987123654"


def test_create_user_token() -> None:
    token, expires_in = create_user_token(USER_ID, VK_USER_ID)

    assert token is not None
    assert expires_in > 0


def test_user_token_payload() -> None:
    token, expires_in = create_user_token(USER_ID, VK_USER_ID)

    decoded_payload = decode_token(token)

    assert decoded_payload is not None
    assert decoded_payload["sub"] == str(USER_ID)
    assert decoded_payload["vk_user_id"] == VK_USER_ID
    assert decoded_payload["type"] == "user"


def test_create_admin_token() -> None:
    token, expires_in = create_admin_token(ADMIN_ID, SESSION_ID)

    assert token is not None
    assert expires_in > 0


def test_decode_invalid() -> None:
    assert decode_token("not-a-jwt") is None
    assert decode_token("") is None
    assert decode_token("a.b.c") is None


def test_decode_tampered_signature() -> None:
    """Подмена значащего символа подписи делает токен недействительным"""
    token, _ = create_user_token(USER_ID, VK_USER_ID)
    header, payload, signature = token.split(".")
    signature = ("a" if signature[0] != "a" else "b") + signature[1:]
    tampered = f"{header}.{payload}.{signature}"
    assert decode_token(tampered) is None


def test_decode_tampered_payload() -> None:
    token, _ = create_user_token(USER_ID, VK_USER_ID)
    header, payload, signature = token.split(".")

    # декодируем payload без верификации (padding важен для base64)
    padding = "=" * (-len(payload) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(payload + padding))
    decoded["sub"] = "999999"  # другой пользователь

    new_payload = base64.urlsafe_b64encode(json.dumps(decoded).encode()).rstrip(b"=").decode()

    forged = f"{header}.{new_payload}.{signature}"
    assert decode_token(forged) is None
