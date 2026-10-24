"""Prometheus-метрики проекта.

HTTP-метрики (RPS, latency, ошибки) генерируются автоматически
через prometheus-fastapi-instrumentator в main.py.

Здесь — бизнес-метрики, которые инкрементируются в сервисах:
- MARKS_CREATED — судейские отметки
- NOTIFICATIONS_SENT — push-уведомления
- CACHE_HITS / CACHE_MISSES — эффективность кэша
- TRACKING_POINTS_INGESTED — точки трека от Iridium
- USER_LOGINS — логины пользователей
- ACTIVE_TRACKERS — трекеры онлайн (gauge)
"""

from prometheus_client import Counter, Gauge

# ─── Счётчики (только растут) ──────────────────────────────────────────────

MARKS_CREATED = Counter(
    "avacha_marks_created_total",
    "Количество созданных судейских отметок",
    ["stage_id"],
)

NOTIFICATIONS_SENT = Counter(
    "avacha_notifications_sent_total",
    "Отправленные уведомления",
    ["status"],  # sent / failed / skipped
)

CACHE_HITS = Counter(
    "avacha_cache_hits_total",
    "Попадания в кэш",
    ["namespace"],  # stages / results / map / dashboard
)

CACHE_MISSES = Counter(
    "avacha_cache_misses_total",
    "Промахи кэша",
    ["namespace"],
)

TRACKING_POINTS_INGESTED = Counter(
    "avacha_tracking_points_total",
    "Точки трека, сохранённые в БД",
    ["source"],  # iridium / manual
)

USER_LOGINS = Counter(
    "avacha_user_logins_total",
    "Логины пользователей",
    ["platform"],  # vk / web
)

# ─── Gauges (могут расти и падать) ─────────────────────────────────────────

ACTIVE_TRACKERS = Gauge(
    "avacha_active_trackers",
    "Трекеры, передающие данные прямо сейчас",
)

SOS_ACTIVE = Gauge(
    "avacha_sos_active",
    "Трекеры с активным сигналом SOS",
)
