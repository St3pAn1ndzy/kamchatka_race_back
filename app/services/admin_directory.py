"""Админский сервис справочников гонки"""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.discipline import Discipline
from app.db.models.season import Season
from app.db.models.stage import Stage
from app.repositories.discipline import DisciplineRepository
from app.repositories.season import SeasonRepository
from app.repositories.stage import StageRepository
from app.schemas.admin_directory import (
    DisciplineCreateRequest,
    DisciplineUpdateRequest,
    SeasonCreateRequest,
    SeasonUpdateRequest,
    StageCreateRequest,
    StageUpdateRequest,
)
from app.services.cache import cache


class AdminDirectoryService:
    """Управляет сезонами, дисциплинами и этапами из админки"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.seasons = SeasonRepository(session)
        self.disciplines = DisciplineRepository(session)
        self.stages = StageRepository(session)

    async def list_seasons(self) -> list[Season]:
        """Просто возращаем список сезонов"""
        return await self.seasons.list_ordered()

    async def create_season(self, body: SeasonCreateRequest, *, admin_id: int) -> Season:
        """Создаем сезон"""
        self._validate_period(
            body.starts_at,
            body.ends_at,
            "Дата окончания сезона не может быть раньше даты начала",
        )

        # Если уже есть, то выкидываем
        existing = await self.seasons.get_by_year(body.year)
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Сезон с таким годом уже существует")

        create_data = body.model_dump()
        audit_data = body.model_dump(mode="json")

        season = Season(**create_data)
        self.session.add(season)
        await self.session.flush()

        # Записываем лог действия
        self._audit(admin_id, "season_created", "season", season.id, {"new": audit_data})
        await self.session.commit()
        await self.session.refresh(season)

        # Инвалидация кэша справочников
        await self._invalidate_directory_cache()

        return season

    async def update_season(
        self,
        season_id: int,
        body: SeasonUpdateRequest,
        *,
        admin_id: int,
    ) -> Season:
        """Обновляем уже имею-ся сезон"""
        season = await self.session.get(Season, season_id)
        # Если сезона нет - выкидываем
        if season is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Сезон не найден")

        old = self._season_payload(season)
        # Берем инфу и делаем 2 действия: 1) обновляем, 2) вносим в лог
        data = body.model_dump(exclude_unset=True)
        audit_data = body.model_dump(exclude_unset=True, mode="json")

        starts_at = data.get("starts_at", season.starts_at)
        ends_at = data.get("ends_at", season.ends_at)
        # Проверяем на корректность начала и конца обновленного сезона
        self._validate_period(
            starts_at,
            ends_at,
            "Дата окончания сезона не может быть раньше даты начала",
        )

        if "year" in data:
            if data["year"] is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, "Год сезона не может быть пустым"
                )
            existing = await self.seasons.get_by_year(data["year"])
            if existing is not None and existing.id != season.id:
                raise HTTPException(status.HTTP_409_CONFLICT, "Сезон с таким годом уже существует")

        # Присваиваем новые значения
        for field, value in data.items():
            setattr(season, field, value)

        await self.session.flush()
        self._audit(
            admin_id, "season_updated", "season", season.id, {"old": old, "new": audit_data}
        )
        await self.session.commit()
        await self.session.refresh(season)

        # Инвалидация кэша справочников — могли изменить is_active
        await self._invalidate_directory_cache()

        return season

    async def list_disciplines(self, *, season_id: int | None = None) -> list[Discipline]:
        """Возращаем просто список дисциплин"""
        if season_id is not None:
            await self._require_season(season_id)

        return await self.disciplines.list_ordered(season_id=season_id)

    async def create_discipline(
        self,
        body: DisciplineCreateRequest,
        *,
        admin_id: int,
    ) -> Discipline:
        """Создаем дисциплину"""
        await self._require_season(body.season_id)
        # Берем дисциплину по сезону и короткому названию
        existing = await self.disciplines.get_by_season_and_code(body.season_id, body.code)
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Дисциплина с таким кодом уже существует в этом сезоне",
            )

        create_data = body.model_dump()
        audit_data = body.model_dump(mode="json")

        discipline = Discipline(**create_data)
        self.session.add(discipline)
        await self.session.flush()

        self._audit(
            admin_id,
            "discipline_created",
            "discipline",
            discipline.id,
            {"new": audit_data},
        )
        await self.session.commit()
        await self.session.refresh(discipline)

        # Инвалидация кэша справочников
        await self._invalidate_directory_cache()

        return discipline

    async def update_discipline(
        self,
        discipline_id: int,
        body: DisciplineUpdateRequest,
        *,
        admin_id: int,
    ) -> Discipline:
        discipline = await self.session.get(Discipline, discipline_id)
        if discipline is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Дисциплина не найдена")

        old = self._discipline_payload(discipline)
        data = body.model_dump(exclude_unset=True)
        audit_data = body.model_dump(exclude_unset=True, mode="json")

        season_id = data.get("season_id", discipline.season_id)
        code = data.get("code", discipline.code)
        if "season_id" in data or "code" in data:
            if season_id is None or code is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "Сезон и код дисциплины не могут быть пустыми",
                )
            await self._require_season(season_id)

            existing = await self.disciplines.get_by_season_and_code(season_id, code)
            if existing is not None and existing.id != discipline.id:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Дисциплина с таким кодом уже существует в этом сезоне",
                )

        for field, value in data.items():
            setattr(discipline, field, value)

        await self.session.flush()
        self._audit(
            admin_id,
            "discipline_updated",
            "discipline",
            discipline.id,
            {"old": old, "new": audit_data},
        )
        await self.session.commit()
        await self.session.refresh(discipline)

        # Инвалидация кэша справочников
        await self._invalidate_directory_cache()

        return discipline

    async def list_stages(self, *, season_id: int | None = None) -> list[Stage]:
        if season_id is not None:
            await self._require_season(season_id)

        return await self.stages.list_ordered(season_id=season_id)

    async def create_stage(self, body: StageCreateRequest, *, admin_id: int) -> Stage:
        await self._require_season(body.season_id)
        existing = await self.stages.get_by_season_and_number(body.season_id, body.number)
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Этап с таким номером уже существует в этом сезоне",
            )
        self._validate_period(
            body.start_time,
            body.finish_time,
            "Финиш этапа не может быть раньше старта",
        )

        create_data = body.model_dump()
        audit_data = body.model_dump(mode="json")

        stage = Stage(**create_data)
        self.session.add(stage)
        await self.session.flush()

        self._audit(admin_id, "stage_created", "stage", stage.id, {"new": audit_data})
        await self.session.commit()
        await self.session.refresh(stage)

        # Инвалидация кэша справочников — добавился новый этап
        await cache.invalidate_pattern("public:stages:*")
        await cache.invalidate_pattern("public:disciplines:*")

        return stage

    async def update_stage(
        self,
        stage_id: int,
        body: StageUpdateRequest,
        *,
        admin_id: int,
    ) -> Stage:
        stage = await self.session.get(Stage, stage_id)
        if stage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Этап не найден")

        old = self._stage_payload(stage)
        data = body.model_dump(exclude_unset=True)
        audit_data = body.model_dump(exclude_unset=True, mode="json")

        if "season_id" in data and data["season_id"] is not None:
            await self._require_season(data["season_id"])

        season_id = data.get("season_id", stage.season_id)
        number = data.get("number", stage.number)
        if "season_id" in data or "number" in data:
            if number is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, "Номер этапа не может быть пустым"
                )
            if season_id is not None:
                existing = await self.stages.get_by_season_and_number(season_id, number)
                if existing is not None and existing.id != stage.id:
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        "Этап с таким номером уже существует в этом сезоне",
                    )

        start_time = data.get("start_time", stage.start_time)
        finish_time = data.get("finish_time", stage.finish_time)
        self._validate_period(
            start_time,
            finish_time,
            "Финиш этапа не может быть раньше старта",
        )

        for field, value in data.items():
            setattr(stage, field, value)

        await self.session.flush()
        self._audit(admin_id, "stage_updated", "stage", stage.id, {"old": old, "new": audit_data})
        await self.session.commit()
        await self.session.refresh(stage)

        # Инвалидация кэша — этап изменился
        await self._invalidate_stage_cache(stage.id)

        return stage

    async def _invalidate_directory_cache(self) -> None:
        """Сброс кэша справочников (этапы, дисциплины)."""
        await cache.invalidate_pattern("public:stages:*")
        await cache.invalidate_pattern("public:disciplines:*")

    async def _invalidate_stage_cache(self, stage_id: int) -> None:
        """Сброс кэша справочников, карты и результатов для этапа."""
        await cache.invalidate_pattern("public:stages:*")
        await cache.invalidate_pattern("public:disciplines:*")
        await cache.invalidate_pattern(f"public:map:model:{stage_id}:*")
        await cache.delete(f"public:map:checkpoint:{stage_id}")
        await cache.invalidate_pattern(f"public:map:track:{stage_id}:*")
        await cache.delete(f"public:results:stage:{stage_id}")
        await cache.delete("public:results:standings")
        await cache.invalidate_pattern("public:results:leaderboard:*")

    async def _require_season(self, season_id: int) -> None:
        season = await self.session.get(Season, season_id)
        if season is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Сезон не найден")

    @staticmethod
    def _validate_period(
        starts_at: datetime | None,
        ends_at: datetime | None,
        message: str,
    ) -> None:
        """Проверяем и выкидываем ошибку в случае неправильных врем-ых рамок"""
        if starts_at is not None and ends_at is not None and ends_at < starts_at:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, message)

    def _audit(
        self,
        admin_id: int,
        action: str,
        entity_type: str,
        entity_id: int,
        payload: dict,
    ) -> None:
        """Обычный лог-аудит"""
        self.session.add(
            AuditLog(
                admin_id=admin_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                payload=payload,
            )
        )

    # Все методы дальше используются для old-new
    @staticmethod
    def _season_payload(season: Season) -> dict:
        return {
            "year": season.year,
            "title": season.title,
            "starts_at": season.starts_at.isoformat() if season.starts_at else None,
            "ends_at": season.ends_at.isoformat() if season.ends_at else None,
            "is_active": season.is_active,
        }

    @staticmethod
    def _discipline_payload(discipline: Discipline) -> dict:
        return {
            "season_id": discipline.season_id,
            "code": discipline.code,
            "name": discipline.name,
            "sort_order": discipline.sort_order,
            "is_active": discipline.is_active,
        }

    @staticmethod
    def _stage_payload(stage: Stage) -> dict:
        return {
            "season_id": stage.season_id,
            "number": stage.number,
            "name": stage.name,
            "distance_km": stage.distance_km,
            "start_time": stage.start_time.isoformat() if stage.start_time else None,
            "finish_time": stage.finish_time.isoformat() if stage.finish_time else None,
            "order_index": stage.order_index,
            "tracker_interval_seconds": stage.tracker_interval_seconds,
            "status": stage.status,
        }
