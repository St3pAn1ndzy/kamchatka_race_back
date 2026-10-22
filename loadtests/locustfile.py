"""Нагрузочные сценарии для Locust.

Эмулирует поведение болельщиков в VK Mini App.
Запуск:
    poetry run locust -f loadtests/locustfile.py --host=http://localhost:8000
"""

import random

from locust import HttpUser, between, task


class ViewerUser(HttpUser):
    """Обычный болельщик в VK Mini App."""

    # Пауза между действиями (2-8 секунд).
    # Имитируем, что человек смотрит на экран, а не спамит запросами.
    wait_time = between(2, 8)

    def on_start(self):
        """Выполняется один раз при старте виртуального пользователя."""
        # Мы не будем логиниться через VK (это сложно мокать),
        # просто запомним случайный ID участника для карточки.
        self.participant_id = random.randint(1, 15)
        self.stage_id = 1  # Берем первый этап

    @task(10)
    def view_map_positions(self):
        """Самый частый сценарий: смотрит на карту (координаты)."""
        self.client.get(
            f"/api/v1/stages/{self.stage_id}/positions", name="/api/v1/stages/[id]/positions"
        )

    @task(5)
    def view_participants_list(self):
        """Листает список участников."""
        self.client.get("/api/v1/participants?limit=20&offset=0", name="/api/v1/participants")

    @task(3)
    def view_participant_card(self):
        """Открывает карточку конкретного участника."""
        self.client.get(
            f"/api/v1/participants/{self.participant_id}", name="/api/v1/participants/[id]"
        )

    @task(3)
    def view_leaders(self):
        """Смотрит рейтинг лидеров."""
        self.client.get(
            f"/api/v1/stages/{self.stage_id}/leaders", name="/api/v1/stages/[id]/leaders"
        )

    @task(2)
    def view_checkpoints(self):
        """Смотрит контрольные пункты на маршруте."""
        self.client.get(
            f"/api/v1/stages/{self.stage_id}/checkpoints", name="/api/v1/stages/[id]/checkpoints"
        )

    @task(1)
    def view_track(self):
        """Смотрит трек (нитку маршрута) - тяжелый GeoJSON."""
        self.client.get(f"/api/v1/stages/{self.stage_id}/track", name="/api/v1/stages/[id]/track")
