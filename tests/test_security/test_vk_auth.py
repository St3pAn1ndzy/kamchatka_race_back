# Тесты vk_auth:
import base64
import hashlib
import hmac

from app.security.vk_auth import verify_vk_launch_params

SECRET = "test_secret_key"


def _make_sign(params: dict[str, str], secret: str = SECRET) -> str:
    """Считает sign так же, как VK и как verify_vk_launch_params."""
    pairs = sorted((k, str(v)) for k, v in params.items() if k.startswith("vk_"))
    sign_str = "&".join(f"{k}={v}" for k, v in pairs)
    digest = hmac.new(
        key=secret.encode(),
        msg=sign_str.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def test_valid_signature() -> None:
    params = {
        "vk_user_id": "192837465",
        "vk_app_id": "12345",
        "vk_platform": "mobile_iphone",
    }
    params["sign"] = _make_sign(params)
    assert verify_vk_launch_params(params, SECRET)


def test_no_sign() -> None:
    params = {"vk_user_id": "192837465"}
    assert not verify_vk_launch_params(params, SECRET)

    # sign есть, но пустой
    assert not verify_vk_launch_params({**params, "sign": ""}, SECRET)


def test_no_vk_keys() -> None:
    params = {"sign": "some_sign", "foo": "bar"}
    assert not verify_vk_launch_params(params, SECRET)


def test_tampered_sign() -> None:
    params = {"vk_user_id": "192837465"}
    params["sign"] = _make_sign(params)
    params["sign"] = params["sign"][:-1] + ("a" if params["sign"][-1] != "a" else "b")
    assert not verify_vk_launch_params(params, SECRET)
