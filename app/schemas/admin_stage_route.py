from itertools import pairwise

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema


class RouteCoordinate(BaseSchema):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)


class StageRouteReplaceRequest(BaseSchema):
    points: list[RouteCoordinate] = Field(min_length=2, max_length=2000)

    @model_validator(mode="after")
    def reject_repeated_neighbors(self) -> "StageRouteReplaceRequest":
        for previous, current in pairwise(self.points):
            if previous == current:
                raise ValueError("Соседние точки маршрута не должны совпадать")
        return self


class StageRoutePointResponse(RouteCoordinate):
    position: int


class StageRouteResponse(BaseSchema):
    stage_id: int
    points: list[StageRoutePointResponse]
