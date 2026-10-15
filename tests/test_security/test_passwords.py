# Тесты passwords: проверяется отработка верификации пароля и хеша,
# а также корректное создание хеша

from app.security.passwords import hash_password, verify_password

PLAIN_PASSWORD = "0p1a2s3s4w5o6r7d8"


def test_hash_and_verify_correct() -> None:
    password_hash = hash_password(PLAIN_PASSWORD)

    assert verify_password(PLAIN_PASSWORD, password_hash)


def test_verify_wrong() -> None:
    wrong_password = "wrOng_0p1a2s3s4w5o6r7d8"
    wrong_password_hash = hash_password(wrong_password)

    assert not verify_password(PLAIN_PASSWORD, wrong_password_hash)


def test_verify_empty() -> None:
    password_hash = hash_password("0p1a2s3s4w5o6r7d8")

    assert not verify_password("", password_hash)


def test_hashes_differ() -> None:
    first_hash_pass = hash_password(PLAIN_PASSWORD)
    second_hash_pass = hash_password(PLAIN_PASSWORD)

    assert first_hash_pass != second_hash_pass
