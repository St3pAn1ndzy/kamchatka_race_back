# Авача — VK Mini App Backend

Бэкенд мини-приложения ВКонтакте для зимнего фестиваля и гонки на собачьих упряжках «Авача» (Камчатка).
Обеспечивает live-трекинг участников, расчёт официальных результатов, карточки каюров и push-уведомления.

## ✨ Ключевые особенности

- **Live-трекинг (Iridium360):** Спутниковый мониторинг упряжек. В ответах API отдаётся статус свежести данных
  (`fresh` / `delayed` / `stale` / `no_data`). Прямой доступ к трекерам закрыт, всё идёт через кэшируемый бэкенд.
- **Высокая нагрузка:** Redis-кэширование горячих эндпоинтов (карта, позиции). API выдерживает **1000+ одновременных
  пользователей** (200+ RPS, p95 < 130ms) на локальной машине. Защита от переполнения БД (строгий `MAX_ID` на все ID).
- **Официальные результаты:** Расчёт протоколов и общего зачёта строго по судейским отметкам (`OfficialMark`). Трекеры
  не используются для времени.
- **Кастомная админ-панель (SQLAdmin):**
    - *Оперативный штаб (Race Control):* Live-таблица с прогрессом участников по дистанции.
    - *Мониторинг оборудования:* Цветовая индикация состояния трекеров и батарей.
    - *Импорт результатов:* Загрузка CSV-протоколов от судей с валидацией и записью в БД.
    - *Центр уведомлений:* Массовая отправка push-сообщений.
- **152-ФЗ:** Логирование с маскировкой чувствительных данных, эндпоинт анонимизации профиля пользователя.

## Стек

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2
- **Фоновые задачи:** Celery, Redis (Broker), Celery Beat
- **БД:** PostgreSQL 16
- **Кэш:** Redis 7
- **Админка:** SQLAdmin + Jinja2 + Tabler UI
- **Инфраструктура:** Docker Compose, Poetry
- **Тестирование:** Pytest, Schemathesis, Locust, Ruff

## Быстрый старт

### Требования

- Python 3.12+
- Poetry
- Docker + Docker Compose

### Установка и запуск

```sh
# 1. Клонируем и ставим зависимости
poetry install

# 2. Поднимаем БД и Redis
docker compose up -d postgres redis

# 3. Настраиваем окружение
cp .env.template .env
# Отредактируйте .env: VK_SECURE_KEY, SECRET_KEY, IRIDIUM_API_KEY

# 4. Применяем миграции
poetry run alembic upgrade head

# 5. Запускаем API
poetry run uvicorn app.main:app --reload
```

**Точки входа:**

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Админ-панель: http://localhost:8000/admin-panel (admin / admin123)
- Health-check: http://localhost:8000/health

**Запуск полного стека:**

```sh
docker compose up --build
```

## 🧪 Тестирование и надежность

Проект покрыт тестами на нескольких уровнях.

### 1. Unit & Integration (Pytest)

Интеграционные тесты используют изоляцию транзакций (`SAVEPOINT`), что позволяет тестировать реальные запросы к БД без
загрязнения данных между тестами.

```sh
poetry run pytest
```

### 2. Fuzz-тестирование (Schemathesis)

Прогон всех эндпоинтов невалидными данными (SQL-инъекции, переполнения, `null`).

```sh
poetry run schemathesis run http://localhost:8000/openapi.json --checks all
```

**Результат:** 3298+ сгенерированных тест-кейсов. **0 ошибок 500 (Server Error).** Все некорректные данные отбиваются
422
Unprocessable Content.

### 3. Нагрузочное тестирование (Locust)

Эмуляция поведения болельщиков в VK Mini App.

```sh
poetry run locust -f loadtests/locustfile.py --host=http://localhost:8000
```

**Результаты (1000 users, Docker Compose prod-конфигурация с 4 воркерами Uvicorn):**

- Пропускная способность: **200.8 RPS**
- Медиана (p50): **3 ms**
- 95-й процентиль (p95): **7 ms**
- Ошибки: **0.01%** (8 из 70 376 запросов — кратковременный спайк при холодном старте).

> *Артефакты тестирования доступны в папке [`docs/`](./docs).*

## 🛠 Админ-панель для организаторов

В проекте развернута кастомная админка на базе SQLAdmin:

- **Дашборд:** SOS-сигналы, метрики гонки, автообновление.
- **Мониторинг:** Таблица трекеров с цветовой индикацией (зеленый/желтый/красный).
- **Race Control:** Таблица лидеров с прогресс-барами.
- **Push Sender:** Форма массовой рассылки.
- **Импорт CSV:** Автоматическое создание судейских отметок из протокола.

## Переменные окружения

Файл `.env.template` содержит все необходимые ключи. Обязательные для запуска: `SECRET_KEY`, `VK_SECURE_KEY`,
`POSTGRES_*`.

| Переменная                       | Назначение                             | По умолчанию |
|----------------------------------|----------------------------------------|--------------|
| `ENV`                            | Окружение (`dev` / `prod`)             | `dev`        |
| `SECRET_KEY`                     | Секрет JWT                             | `change-me`  |
| `VK_APP_ID` / `VK_SECURE_KEY`    | Параметры VK Mini App                  | —            |
| `IRIDIUM_API_KEY`                | Ключ доступа к спутниковым трекерам    | —            |
| `TRACKING_POLL_INTERVAL_SECONDS` | Интервал опроса Iridium (сек)          | `900`        |
| `CACHE_TTL_STAGES`               | TTL кэша справочников (сек)            | `3600`       |
| `CACHE_TTL_RESULTS`              | TTL кэша протоколов (сек)              | `300`        |
| `CACHE_TTL_MAP`                  | TTL кэша позиций на карте (сек)        | `15`         |
| `CACHE_TTL_STATS`                | TTL кэша статистики для дашборда (сек) | `30`         |

## Структура проекта

```text
app/
  main.py              # create_app(), middleware
  config.py            # Pydantic Settings
  enums.py             # Все Enums
  api/                 # Роутеры (v1/ и admin/)
  services/            # Бизнес-логика (кэш, трекинг, результаты)
  repositories/        # Слой доступа к данным (SQLAlchemy)
  db/                  # Base, engine, модели
  schemas/             # Pydantic схемы
  security/            # JWT, VK Auth, Admin Sessions
  integrations/        # Клиенты Iridium360 и VK API
  tasks/               # Celery задачи (пуши, парсинг Iridium)
  admin_panel/         # Кастомная админка (views, templates)
alembic/versions/      # Миграции
loadtests/             # Скрипты Locust
tests/                 # Pytest + Schemathesis
docs/                  # Скриншоты нагрузочных тестов
```

## Тестовые данные (Seed)

```sh
# Очистить БД и заполнить тестовыми данными (15 каюров, треки, отметки, юзеры)
poetry run python -m scripts.seed_mock --reset
```

**Админ:** `admin` / `admin123`. *Работает только при `ENV=dev`.*

## Ссылки

- Официальное сообщество гонки: https://vk.ru/avacha.race