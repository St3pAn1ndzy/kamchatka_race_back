"""Хеширование и проверка паролей администраторов"""

from passlib.context import CryptContext

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Проверяем открытый пароль против bcrypt-хеша"""
    return _password_context.verify(plain_password, password_hash)


def hash_password(plain_password: str) -> str:
    """Создаем bcrypt-хеш для хранения в базе"""
    return _password_context.hash(plain_password)
