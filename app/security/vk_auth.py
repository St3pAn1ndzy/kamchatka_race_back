import base64
import hashlib
import hmac


def verify_vk_launch_params(params: dict, secret: str) -> bool:
    """Проверка подписи launch_params VK Mini Apps.

    Алгоритм (vk.com/dev/vk_apps_launch_params):
      1. Берём все ключи, начинающиеся с "vk_".
      2. Сортируем их по алфавиту.
      3. Склеиваем через "&" в формате key=value.
      4. Считаем HMAC-SHA256 от этой строки, секрет = secure key приложения.
      5. Кодируем digest в base64url без padding.
      6. Сравниваем с параметром sign (base64url, без padding).
    """
    if not params or "sign" not in params:
        return False

    sign = str(params.get("sign", "")).strip()
    if not sign:
        return False

    pairs = []
    for key, value in params.items():
        if key.startswith("vk_"):
            pairs.append((key, str(value)))

    if not pairs:
        return False

    pairs.sort(key=lambda kv: kv[0])
    sign_str = "&".join(f"{k}={v}" for k, v in pairs)

    digest = hmac.new(
        key=secret.encode("utf-8"),
        msg=sign_str.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    expected = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    return hmac.compare_digest(expected, sign)
