"""Объединяем миграции высот маршрута и категорий зрительских локаций"""

revision = "c63f2910ab82"
down_revision = ("b18c24a901ef", "21661dda6550")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Объединяет ветки без дополнительных изменений таблиц"""
    pass


def downgrade() -> None:
    """Возвращает две предшествующие версии миграций"""
    pass
