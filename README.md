# Авача — VK Mini App Backend

Бэкенд мини-приложения ВКонтакте для фестиваля и гонки на собачьих упряжках «Авача»: трекинг участников, судейские результаты, новости и программа мероприятий

[Запуск](#запуск) · [Админка](#админка-и-импорт-маршрутов) · [Демонстрация](#демонстрация-админки) · [Проверки](#проверки) · [Production](#production) · [Структура проекта](#структура-проекта)

## Возможности

- **Live-трекинг:** координаты Iridium360, скорость, прогресс и свежесть данных (`fresh`, `delayed`, `stale`, `no_data`)
- **Официальные результаты:** протоколы этапов и общий зачёт по судейским отметкам, GPS не определяет время прохождения КП
- **Админка:** оперативный штаб, SOS, оборудование, участники и журнал действий
- **Маршруты:** импорт KML/GPX с контрольными пунктами и перенос трассы во время этапа
- **Контент:** новости, программа фестиваля, FAQ, зрительские локации и push-рассылки
- **Инфраструктура:** Redis-кеширование, метрики Prometheus и дашборд Grafana

## Стек

- **Backend:** Python 3.12, FastAPI, Pydantic 2
- **База данных:** PostgreSQL 16, SQLAlchemy 2 async, Alembic
- **Кеш:** Redis 7
- **Фоновые задачи:** Celery, Celery Beat, Redis как брокер
- **Админка:** SQLAdmin, Jinja2, Tabler UI, Яндекс Карты
- **Интеграции:** Iridium360, API ВКонтакте
- **Мониторинг:** Prometheus, Grafana
- **Инфраструктура:** Docker Compose, Poetry, GitHub Actions
- **Проверки:** Pytest, Node.js 22, Ruff, Schemathesis, Locust

## Запуск

Команды выполняются из корня проекта, Docker должен быть запущен

**Требования:** Docker с Compose и поддержкой `--wait`; для запуска Python на хосте, демоскриптов и проверок — Python 3.12+, Poetry 2 с поддержкой `[dependency-groups]`, для JavaScript-тестов — Node.js 22

### 1. Настроить окружение

```sh
test -f .env || cp .env.template .env
```

Для локальной работы оставьте `ENV=dev`; если порт PostgreSQL 5432 занят, укажите `POSTGRES_PORT=5433` в `.env`

### 2. Поднять PostgreSQL и Redis

```sh
docker compose up -d --wait postgres redis
```

### 3. Собрать API и применить миграции

```sh
docker compose build api
docker compose run --rm --no-deps api alembic upgrade head
```

### 4. Добавить тестовые данные — при необходимости

```sh
docker compose run --rm --no-deps api python -m scripts.seed_mock
```

Seed создаёт шесть этапов, 15 участников, маршруты, GPS-точки и судейские отметки

Локальный вход в админку: `admin / admin123`; флаг `--reset` очищает текущую базу перед заполнением

### 5. Запустить API

```sh
docker compose up -d api
```

| Сервис | Адрес |
| --- | --- |
| Swagger | http://localhost:8000/docs |
| Админка | http://localhost:8000/admin-panel |
| Проверка ответа API | http://localhost:8000/health |
| Метрики | http://localhost:8000/metrics |

### 6. Подключить фоновые задачи и мониторинг — при необходимости

```sh
docker compose up --build -d worker beat prometheus grafana
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001, локальный вход `admin / admin`
- В dev Grafana добавьте источник Prometheus `http://prometheus:9090`, если он ещё не настроен

Worker и Beat нужны для периодического опроса Iridium и обработки уведомлений

При `ENV=dev` и пустом `IRIDIUM_API_KEY` используется mock-клиент; для реальных интеграций заполните параметры Iridium и ВК в `.env`

### API вне Docker

Создайте `.env` по шагу 1, задайте `POSTGRES_HOST=localhost` и `REDIS_HOST=localhost`; порты должны совпадать с опубликованными портами Compose

```sh
poetry install --with dev
docker compose up -d --wait postgres redis
poetry run alembic upgrade head
docker compose stop api
poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Для фоновых задач используйте `docker compose up --build -d worker beat`; Prometheus из Compose запускает также контейнер API, который займёт тот же порт 8000

### Полезные команды

| Действие | Команда |
| --- | --- |
| Состояние контейнеров | `docker compose ps` |
| Логи API | `docker compose logs --tail=100 -f api` |
| Логи фоновых задач | `docker compose logs --tail=100 -f worker beat` |
| Остановить контейнеры | `docker compose stop` |

После обновления кода с зависимостями или миграциями:

```sh
docker compose stop api worker beat
docker compose build api worker beat
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d api worker beat
```

## Админка и импорт маршрутов

Вход: http://localhost:8000/admin-panel, локальные реквизиты после seed — `admin / admin123`

| Раздел | Назначение |
| --- | --- |
| Дашборд и оперативный штаб | SOS, карта, позиции и прогресс участников |
| Участники и трекеры | Карточки, статусы, назначение устройств и контроль связи |
| Отметки и протоколы | Ввод судейского времени, отмена ошибочных отметок и публикация результатов |
| Гонка и маршрут | Просмотр этапов, предпросмотр и импорт KML/GPX |
| Контент и рассылки | Новости, программа, справочная информация и очередь push-уведомлений |
| Журнал аудита | История административных изменений |

Для импорта откройте «Гонка и маршрут», загрузите файл, проверьте предпросмотр и подтвердите сохранение

- **Маршрут с КП:** до 8 МиБ, сопоставление линий существующим этапам, выбор направления и типов КП
- **Только линия:** до 2 МиБ и 2000 точек, координаты существующих КП не меняются
- **Во время этапа:** допускается перенос линии и существующих КП с сохранением их названий, типов и количества; отметки и GPS-история сохраняются
- **Завершённый этап:** изменение маршрута запрещено

CSV-импорт судейских таблиц пока не подключён к панели

Порядок работы сотрудников описан в [руководстве по админке](docs/staff-guide.md)

## Демонстрация админки

| Профиль | Адрес админки | PostgreSQL / Redis DB | Данные |
| --- | --- | --- | --- |
| `overview` | http://127.0.0.1:8000/admin-panel | `avacha_demo_overview` / `13` | Три этапа с маршрутами, GPS и отметками |
| `route-import` | http://localhost:8001/admin-panel | `avacha_demo_import` / `14` | Шесть этапов без маршрутов, КП, GPS и отметок для показа импорта |

**1. Подготовить оба профиля** — в `.env` нужны `ENV=dev`, `POSTGRES_HOST=localhost` и `REDIS_HOST=localhost`

```sh
poetry install --with dev
docker compose up -d --wait postgres redis
docker compose stop api
poetry run python -m scripts.demo prepare
```

Повторная подготовка сохраняет данные; `prepare --reset` очищает и заново заполняет обе демобазы

**2. Запустить серверы в разных терминалах**

```sh
# Терминал 1 — обзор админки
poetry run python -m scripts.demo serve overview
```

```sh
# Терминал 2 — импорт маршрута
poetry run python -m scripts.demo serve route-import
```

Используйте адреса из таблицы: разные имена хоста разделяют cookie входа; не запускайте обычный контейнер API поверх демосерверов

**3. Показать движение с SOS** — откройте карту обзорной админки и запустите в третьем терминале:

```sh
poetry run python -m scripts.demo move --device-id 1 --steps 24 --interval 5 --sos-at 6
```

`device-id` — ID трекера; SOS включается на шестом шаге, при штатном завершении скрипт удаляет свои GPS-точки

### Сценарии фронтенда

В `ENV=dev` доступны `GET /api/v1/dev/scenarios/` и `POST /api/v1/dev/scenarios/{name}` с именами `upcoming`, `live`, `finished`

| Сценарий | Состояние приложения |
| --- | --- |
| `upcoming` | Этапы запланированы, участники зарегистрированы, GPS-точек нет |
| `live` | Первый этап завершён, второй идёт, участники отображаются на трассе |
| `finished` | Все этапы завершены, добавлен анонс следующей гонки |

> Переключение сценария очищает всю базу подключённого API, включая пользователей и администраторов — используйте отдельный тестовый экземпляр, доступ не защищён авторизацией

Это отдельный режим, не запускайте его в базах двух демонстраций админки

## Проверки

Требуются зависимости `poetry install --with dev`, Node.js 22 и запущенные PostgreSQL и Redis

Один раз создайте тестовую базу, при нестандартных реквизитах замените роль и имя:

```sh
docker compose exec postgres createdb -U avacha avacha_test
```

В `pyproject.toml` для тестов заданы `ENV=test`, `POSTGRES_DB=avacha_test` и `REDIS_DB=15`; схема этой базы пересоздаётся, кеш очищается — не запускайте прогоны параллельно на одних ресурсах

```sh
poetry run pytest -q
node --test tests/js/*.test.cjs
poetry run ruff check app/ tests/
poetry run ruff format --check app/ tests/
poetry run python -m scripts.export_openapi
```

CI проверяет Ruff, Pytest, JavaScript и генерацию OpenAPI

Дополнительные проверки на отдельном тестовом экземпляре API:

```sh
poetry run schemathesis run http://localhost:8000/openapi.json --include-method GET --checks all
poetry run locust -f loadtests/locustfile.py --host=http://localhost:8000
```

Locust использует участников с ID 1–15 и этап с ID 1; результаты прошлого прогона: [статистика](docs/load-test-prod-stats.png) и [графики](docs/load-test-prod-charts.png)

## Мониторинг

Prometheus собирает метрики с `api:8000/metrics` каждые 10 секунд, дашборд Grafana хранится в `monitoring/dashboards/avacha.json`

- HTTP: частота запросов, время ответа и ошибки
- Бизнес-метрики: попадания и промахи кеша, судейские отметки, уведомления, входы пользователей и точки трекеров
- Просмотр: Grafana → Dashboards → Avacha → Avacha Backend

В dev источник Prometheus подключается вручную, в production Compose настроен provisioning источника и дашборда

Настройка сбора метрик рассчитана на API в Docker; для локального Uvicorn измените адрес в `monitoring/prometheus.yml`

## Production

В `.env` настройте секреты, пароли, доступы ВК и Iridium, CORS и адрес доверенного прокси `FORWARDED_ALLOW_IPS`; демонстрационные пароли замените

```sh
docker compose -f docker-compose.prod.yml build api worker beat
docker compose -f docker-compose.prod.yml up -d --wait postgres redis
docker compose -f docker-compose.prod.yml run --rm --no-deps api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d api worker beat prometheus grafana
```

Конфигурация запускает четыре процесса Uvicorn и Celery с concurrency 4; миграции применяются отдельно, TLS, домен и резервное копирование настраиваются вне Compose

Grafana доступна на сервере по `127.0.0.1:3001`, удалённый доступ — через SSH-туннель:

```sh
ssh -L 3001:localhost:3001 user@server
```

## Переменные окружения

Локальные значения — в [.env.template](.env.template), полный список настроек — в [app/config.py](app/config.py)

| Параметры | Назначение |
| --- | --- |
| `ENV`, `DEBUG` | Окружение и режим отладки; production Compose задаёт `prod` и `false` |
| `POSTGRES_*`, `REDIS_*` | Подключения к БД и кешу |
| `CELERY_BROKER_DB`, `CELERY_RESULT_DB` | Redis DB для задач и результатов Celery |
| `SECRET_KEY`, `ADMIN_PANEL_SESSION_SECRET` | Секреты JWT и сессии админки |
| `VK_*`, `IRIDIUM_*` | Доступы и параметры внешних API |
| `CORS_ORIGINS`, `CORS_ORIGIN_REGEX` | Разрешённые источники запросов фронтенда |
| `TRACKING_POLL_INTERVAL_SECONDS` | Интервал опроса Iridium, по умолчанию 900 секунд |
| `CACHE_TTL_*` | Время жизни кеша |
| `ADMIN_LOGIN_MAX_ATTEMPTS`, `ADMIN_LOGIN_WINDOW_SECONDS` | Общий лимит входа: по умолчанию 10 попыток за 60 секунд с одного IP |
| `FORWARDED_ALLOW_IPS` | Адреса доверенного прокси в production Compose |
| `GRAFANA_ADMIN_*`, `GRAFANA_ROOT_URL` | Учётная запись и адрес Grafana в production Compose |

## Структура проекта

```text
app/
  main.py             # Создание FastAPI, middleware и подключение роутеров
  config.py           # Настройки окружения
  metrics.py          # Метрики Prometheus
  enums.py            # Статусы и перечисления
  api/                # Публичные, административные и сервисные маршруты
  admin_panel/        # Экраны и формы SQLAdmin
  services/           # Трекинг, результаты, импорт, кеш и другая бизнес-логика
  repositories/       # Запросы к данным через SQLAlchemy
  db/                 # Подключения и модели БД
  schemas/            # Схемы запросов и ответов Pydantic
  security/           # Авторизация, сессии и защита входа
  integrations/       # Клиенты Iridium360 и ВКонтакте
  tasks/              # Задачи Celery
  templates/          # HTML-шаблоны админки
  static/             # Стили и JavaScript админки
alembic/versions/     # Миграции БД
scripts/             # Seed, демосерверы, движение участников и экспорт OpenAPI
  scenarios/          # Данные для сценариев фронтенда
data/                # Исходные данные маршрутов
media/               # Загруженные изображения
monitoring/          # Конфигурации Prometheus и Grafana, дашборды
loadtests/           # Нагрузочный сценарий Locust
tests/               # Тесты API, сервисов, репозиториев, интеграций и JavaScript
docs/                # Руководство сотрудников и результаты нагрузочных тестов
.github/workflows/   # Проверки CI
```

## Если запуск не получился

| Проблема | Решение |
| --- | --- |
| Нет модуля `sqlalchemy` | Выполните `poetry install --with dev`, проверьте `poetry env info --executable`; выйдите из чужого активного окружения перед установкой |
| Порт 8000 занят | Остановите контейнер API или второй Uvicorn |
| Не найдена таблица или столбец | Примените `alembic upgrade head` к базе запущенного API |
| В демо нет линии маршрута | Для обзора используйте `overview`; `route-import` изначально пустой |
| Ошибка входа 429 / 503 | При 429 дождитесь `Retry-After`, при 503 проверьте Redis |

Официальное сообщество гонки: [vk.ru/avacha.race](https://vk.ru/avacha.race)
