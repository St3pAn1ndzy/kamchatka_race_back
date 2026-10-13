# Авача — VK Mini App

Бэкенд мини-приложения ВКонтакте для зимнего фестиваля «Берингия» и гонки на собачьих упряжках «Авача» (Камчатка): live-трекинг участников, результаты, карточки каюров и push-уведомления.

## Что внутри

- **Live-трекинг.** Положение участников на карте по данным спутниковых трекеров Iridium360. В ответах карты — статус свежести данных (`fresh` / `delayed` / `stale` / `no_data`). Трекеры доступны только через бэкенд, не напрямую из фронта.
- **Участники.** Карточки каюров, кнопка «Болею за», счётчик болельщиков и рейтинг народной поддержки с динамикой за сутки.
- **Результаты.** Сводная таблица лидеров, протоколы этапов, время на контрольных пунктах, штрафы и обязательные остановки. Официальное время — только судейские отметки (`OfficialMark`), трекер не считается источником времени.
- **Контент и админка.** Расписание гонки и программы фестиваля, новости, FAQ, зрительские локации. Для организаторов — админ-API и SQLAdmin-панель: участники, этапы, отметки, мониторинг трекеров. SOS-сигнал отображается только в админ-API.

## Стек

- Backend: Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic 2, Celery, uvicorn, SQLAdmin
- БД: PostgreSQL 16, Redis 7
- Инфраструктура: Docker Compose (postgres, redis, api, worker, beat), Poetry, GitHub Actions (ruff + генерация `openapi.json`)

## Быстрый старт

### Требования

- Python 3.12+
- Poetry
- Docker + Docker Compose (для PostgreSQL и Redis)

### Установка

```sh
poetry install
docker compose up -d postgres redis
cp .env.template .env
poetry run alembic upgrade head
```

После установки заполнить `.env` — минимум `SECRET_KEY`, `VK_APP_ID`, `VK_SECURE_KEY` (см. раздел «Переменные окружения»).

### Запуск

```sh
poetry run uvicorn app.main:app --reload
```

Приложение: <http://localhost:8000>
Swagger: <http://localhost:8000/docs>
Redoc: <http://localhost:8000/redoc>
Админ-панель SQLAdmin: <http://localhost:8000/admin-panel>
Health-check: <http://localhost:8000/health>

Полный стек с фоном (API + Celery worker + beat):

```sh
docker compose up
```

## Переменные окружения

Файл-шаблон: `.env.template`. Дефолты — из `app/config.py`. Обязательные для запуска помечены «да».

| Переменная | Назначение | Обязательна | По умолчанию |
|---|---|---|---|
| `ENV` | Окружение; сид БД работает только в `dev` | нет | `dev` |
| `DEBUG` | Режим отладки (логи, https_only для cookie) | нет | `true` |
| `SECRET_KEY` | Секрет для подписи JWT | да | `change-me` |
| `API_HOST` / `API_PORT` | Адрес uvicorn | нет | `0.0.0.0` / `8000` |
| `POSTGRES_HOST` / `POSTGRES_PORT` | Хост и порт PostgreSQL | нет | `localhost` / `5432` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Учётка и база PostgreSQL | нет | `avacha` / `avacha` / `avacha` |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` | Redis для Celery | нет | `localhost` / `6379` / `0` |
| `CELERY_BROKER_DB` / `CELERY_RESULT_DB` | Номера баз Redis для брокера и результатов | нет | `1` / `2` |
| `VK_APP_ID` | ID приложения VK Mini App | да | пусто |
| `VK_GROUP_ID` | ID сообщества ВКонтакте | нет | пусто |
| `VK_SECURE_KEY` | Секретный ключ для проверки launch params | да | пусто |
| `VK_SERVICE_TOKEN` | Сервисный токен VK API (интеграции) | для интеграций | пусто |
| `VK_API_VERSION` | Версия VK API | нет | `5.199` |
| `IRIDIUM_BASE_URL` | Базовый URL API Iridium360 | нет | `https://api.iridium360.ru` |
| `IRIDIUM_API_KEY` | Ключ доступа Iridium360 | для трекинга | пусто |
| `TRACKING_POLL_INTERVAL_SECONDS` | Интервал опроса Iridium (сек) | нет | `900` |
| `TRACKING_STALE_MISSED_INTERVALS` | Сколько пропущенных интервалов до статуса «устарело» | нет | `2` |
| `NOTIFICATION_RATE_LIMIT_PER_HOUR` / `_PER_DAY` | Лимиты push-уведомлений | нет | `2` / `10` |
| `ADMIN_PANEL_SESSION_SECRET` | Секрет cookie-сессий SQLAdmin | да (в проде) | `change-me-admin-panel` |
| `ADMIN_SESSION_TTL_SECONDS` | Время жизни админ-сессии (сек) | нет | `28800` |
| `JWT_ALGORITHM` / `JWT_USER_TTL_SECONDS` | Параметры JWT пользователя | нет | `HS256` / `86400` |
| `CORS_ORIGINS` | Разрешённые origin для CORS | нет | vk.com, m.vk.com, prod-apps.vkusercontent.com |
| `PRIVACY_POLICY_VERSION` | Версия политики конфиденциальности (152-ФЗ) | нет | `1.0` |

## Тестовые данные (dev)

Скрипт `scripts/seed_mock.py` заполняет dev-БД: сезон «Авача 2027», три дисциплины, три этапа, контрольные пункты, 15 каюров, трекеры, треки и судейские отметки, болельщиков с подписками «Болею за», push-подписки, очередь уведомлений, новости, расписание, FAQ и зрительские локации. При повторном запуске существующие данные не дублируются. Работает только при `ENV=dev` (без `--force` завершится ошибкой).

```sh
poetry run python -m scripts.seed_mock
poetry run python -m scripts.seed_mock --reset
poetry run python -m scripts.seed_mock --users 50 --no-track
```

Флаги:

- `--reset` — очистить таблицы перед наполнением
- `--users N` — число болельщиков (по умолчанию 30)
- `--no-track` — без треков, маршрутов и судейских отметок
- `--force` — разрешить запуск вне `ENV=dev`

Тестовый администратор: `admin` / `admin123`. В конце скрипт печатает тестовый JWT первого пользователя.

## Структура проекта

```text
app/
  main.py              # create_app(), middleware, lifespan
  config.py            # Settings(BaseSettings)
  enums.py             # все Enum проекта
  admin_panel.py       # представления SQLAdmin
  admin_auth.py        # авторизация SQLAdmin через admin-сессии
  api/
    deps.py            # зависимости: сессии, auth, репозитории
    middleware.py      # RequestID, Logging
    health.py          # GET /health
    v1/                # публичный API /api/v1 (по одному файлу на фичу)
    admin/             # админ-API /api/v1/admin (SOS только здесь)
  services/            # бизнес-логика
  repositories/        # доступ к БД (SQLAlchemy)
  db/
    base.py            # Base, engine, async_sessionmaker
    models/            # один файл = одна модель
  schemas/             # Pydantic-схемы
  security/            # JWT, VK launch params, пароли, admin-сессии
  integrations/        # внешние API: Iridium360 и VK
  tasks/               # Celery app + задачи (уведомления, опрос Iridium)
alembic/versions/      # миграции
scripts/
  seed_mock.py         # заполнение dev-БД тестовыми данными
  export_openapi.py    # генерация openapi.json
tests/                 # pytest: unit-уровень, моки БД и клиентов
```

## API

Полная спецификация — Swagger: `/docs`

## Разработка

### Линтеры и форматирование

```sh
poetry run ruff check app/ tests/
poetry run ruff format app/ tests/
```

В CI: `ruff check app/` и `ruff format --check app/`.

### Тесты

```sh
poetry run pytest
```

Тесты — unit-уровень, мокают БД и внешние клиенты.

### Миграции

```sh
poetry run alembic revision --autogenerate -m "..."
poetry run alembic upgrade head
```

## Ссылки
- Официальное сообщество гонки: https://vk.ru/avacha.race
