"""Безопасное чтение этапов гонки из KML и GPX

Каждый этап содержит name, points, checkpoints и warnings
У каждой точки всегда есть lat, lon и elevation, неизвестная высота равна None
Порядок линий и контрольных точек сохраняется, координаты не округляются
Неоднозначные привязки, неподдерживаемые структуры и соседние точки с одинаковыми
широтой и долготой отклоняются, даже если у таких точек различаются высоты
Ограничения: 8 МиБ, 32 этапа, 2–20000 точек линии, 100 КП на этап,
100000 координат суммарно с учётом КП и 255 символов в названии
"""

import math
import re
from dataclasses import dataclass
from pathlib import PurePath
from xml.etree.ElementTree import Element, ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.services.route_file import RouteFileError

MAX_RACE_ROUTE_FILE_BYTES = 8 * 1024 * 1024
MAX_STAGE_POINTS = 20000
MAX_TOTAL_POINTS = 100000
MAX_STAGES = 32
MAX_CHECKPOINTS = 100
MAX_NAME_LENGTH = 255

_KML_NS = "http://www.opengis.net/kml/2.2"
_GPX_NS = {"http://www.topografix.com/GPX/1/0", "http://www.topografix.com/GPX/1/1"}
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")

# Белые списки проверяют положение каждого элемента, включая игнорируемое оформление
_KML_CHILDREN = {
    "kml": {"Document", "Folder", "Placemark"},
    "Document": {
        "name",
        "description",
        "visibility",
        "open",
        "Style",
        "StyleMap",
        "Folder",
        "Placemark",
    },
    "Folder": {
        "name",
        "description",
        "visibility",
        "open",
        "Style",
        "StyleMap",
        "Folder",
        "Placemark",
    },
    "Placemark": {
        "name",
        "description",
        "visibility",
        "Style",
        "StyleMap",
        "styleUrl",
        "LineString",
        "Point",
    },
    "LineString": {"coordinates", "tessellate", "extrude", "altitudeMode"},
    "Point": {"coordinates", "extrude", "altitudeMode"},
    "Style": {"IconStyle", "LabelStyle", "LineStyle", "PolyStyle", "BalloonStyle", "ListStyle"},
    "StyleMap": {"Pair"},
    "Pair": {"key", "styleUrl", "Style"},
    "IconStyle": {"color", "colorMode", "scale", "heading", "Icon", "hotSpot"},
    "Icon": {"href"},
    "LabelStyle": {"color", "colorMode", "scale"},
    "LineStyle": {"color", "colorMode", "width"},
    "PolyStyle": {"color", "colorMode", "fill", "outline"},
    "BalloonStyle": {"bgColor", "textColor", "text", "displayMode"},
    "ListStyle": {"listItemType", "bgColor", "ItemIcon"},
    "ItemIcon": {"state", "href"},
}
_KML_REPEATED = {"Folder", "Placemark", "Style", "StyleMap", "Pair", "ItemIcon"}
_POINT_METADATA = {
    "ele",
    "time",
    "magvar",
    "geoidheight",
    "name",
    "cmt",
    "desc",
    "src",
    "link",
    "url",
    "urlname",
    "sym",
    "type",
    "fix",
    "sat",
    "hdop",
    "vdop",
    "pdop",
    "ageofdgpsdata",
    "dgpsid",
}
_GPX_CHILDREN = {
    "gpx": {
        "metadata",
        "wpt",
        "rte",
        "trk",
        "name",
        "desc",
        "author",
        "email",
        "url",
        "urlname",
        "time",
        "keywords",
        "bounds",
    },
    "metadata": {"name", "desc", "author", "copyright", "link", "time", "keywords", "bounds"},
    "author": {"name", "email", "link"},
    "copyright": {"year", "license"},
    "link": {"text", "type"},
    "rte": {"name", "cmt", "desc", "src", "link", "url", "urlname", "number", "type", "rtept"},
    "trk": {"name", "cmt", "desc", "src", "link", "url", "urlname", "number", "type", "trkseg"},
    "trkseg": {"trkpt"},
    "wpt": _POINT_METADATA,
    "rtept": _POINT_METADATA,
    "trkpt": _POINT_METADATA,
}
_GPX_REPEATED = {"wpt", "rte", "trk", "rtept", "trkseg", "trkpt", "link"}


def _local(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        namespace, name = tag[1:].split("}", 1)
        return namespace, name
    return "", tag


def _children(element: Element, name: str) -> list[Element]:
    return [child for child in element if _local(child.tag)[1] == name]


def _text(element: Element, name: str) -> str | None:
    children = _children(element, name)
    return children[0].text if children else None


def _name(element: Element, fallback: str) -> str:
    return (_text(element, "name") or "").strip() or fallback


def _validate_tree(root: Element, namespace: str, kml: bool) -> None:
    allowed = _KML_CHILDREN if kml else _GPX_CHILDREN
    repeated = _KML_REPEATED if kml else _GPX_REPEATED
    stack = [(root, 1)]
    count = 0
    while stack:
        element, depth = stack.pop()
        count += 1
        if depth > 64 or count > 500000:
            raise RouteFileError("Превышена допустимая сложность XML")
        current_namespace, name = _local(element.tag)
        if current_namespace != namespace or any(key.startswith("{") for key in element.attrib):
            raise RouteFileError("Посторонние пространства имён запрещены")
        if name == "name" and len((element.text or "").strip()) > MAX_NAME_LENGTH:
            raise RouteFileError("Название не должно превышать 255 символов")
        # В GPX 1.0 author является текстовым полем
        if (
            name in allowed
            and (element.text or "").strip()
            and (kml or name != "author" or len(element))
        ):
            raise RouteFileError("Текст вне полей метаданных не поддерживается")
        seen = set()
        for child in element:
            child_name = _local(child.tag)[1]
            if child_name not in allowed.get(name, set()):
                raise RouteFileError("Неподдерживаемая структура файла маршрута")
            if child_name in seen and child_name not in repeated:
                raise RouteFileError("Повторяющиеся одиночные поля маршрута запрещены")
            seen.add(child_name)
            if (child.tail or "").strip():
                raise RouteFileError("Текст вне полей метаданных не поддерживается")
            stack.append((child, depth + 1))


def _number(value: str | None) -> float:
    value = (value or "").strip()
    if not _NUMBER.fullmatch(value):
        raise RouteFileError("Координаты и высоты должны быть конечными числами")
    number = float(value)
    if not math.isfinite(number):
        raise RouteFileError("Координаты и высоты должны быть конечными числами")
    return number


def _coordinate(lat: str | None, lon: str | None, elevation: str | None) -> dict:
    latitude, longitude = _number(lat), _number(lon)
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise RouteFileError("Широта должна быть от -90 до 90, долгота от -180 до 180")
    return {
        "lat": latitude,
        "lon": longitude,
        "elevation": None if elevation is None else _number(elevation),
    }


def _append_point(points: list[dict], point: dict) -> None:
    if len(points) >= MAX_STAGE_POINTS:
        raise RouteFileError("Линия этапа не должна содержать больше 20000 точек")
    if points and all(points[-1][axis] == point[axis] for axis in ("lat", "lon")):
        raise RouteFileError("Соседние координаты линии не должны совпадать")
    points.append(point)


def _kml_points(geometry: Element, is_line: bool) -> list[dict]:
    coordinates = _children(geometry, "coordinates")
    if len(coordinates) != 1:
        raise RouteFileError("Геометрия KML должна содержать одно поле coordinates")
    points = []
    for token in (coordinates[0].text or "").split():
        values = token.split(",")
        if len(values) not in (2, 3):
            raise RouteFileError("Координаты KML должны иметь вид долгота,широта[,высота]")
        point = _coordinate(values[1], values[0], values[2] if len(values) == 3 else None)
        if is_line:
            _append_point(points, point)
        elif points:
            raise RouteFileError("Контрольная точка KML должна содержать одну координату")
        else:
            points.append(point)
    if not points:
        raise RouteFileError("Геометрия KML не содержит координат")
    return points


def _distance(a: dict, b: dict) -> float:
    """Сферическое расстояние без масштаба для сравнения концов линии"""
    lat_a, lat_b = math.radians(a["lat"]), math.radians(b["lat"])
    return (
        math.sin((lat_b - lat_a) / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(math.radians(b["lon"] - a["lon"]) / 2) ** 2
    )


@dataclass
class _Budget:
    stages: int = 0
    points: int = 0

    def stage(self, name: str, points: list[dict], checkpoints: list[dict]) -> dict:
        if len(points) < 2:
            raise RouteFileError("Линия этапа должна содержать от 2 до 20000 точек")
        if len(checkpoints) > MAX_CHECKPOINTS:
            raise RouteFileError("На этапе допускается не более 100 контрольных точек")
        self.stages += 1
        self.points += len(points) + len(checkpoints)
        if self.stages > MAX_STAGES:
            raise RouteFileError("Допускается не более 32 этапов")
        if self.points > MAX_TOTAL_POINTS:
            raise RouteFileError("Суммарно допускается не более 100000 координат, включая КП")
        warnings = []
        if checkpoints and _distance(checkpoints[0], points[-1]) < _distance(
            checkpoints[0], points[0]
        ):
            warnings.append(
                "Первый контрольный пункт ближе к концу линии, чем к началу: "
                "проверьте направление этапа, порядок точек сохранён"
            )
        return {"name": name, "points": points, "checkpoints": checkpoints, "warnings": warnings}


def _parse_kml(root: Element, budget: _Budget) -> list[dict]:
    stages = []

    def visit(container: Element) -> None:
        placemarks = _children(container, "Placemark")
        folders = _children(container, "Folder") + _children(container, "Document")
        if placemarks and folders:
            raise RouteFileError("Точки и линии должны находиться в отдельной папке этапа")
        if placemarks:
            lines, checkpoints = [], []
            for placemark in placemarks:
                geometry = [
                    child for child in placemark if _local(child.tag)[1] in {"LineString", "Point"}
                ]
                if len(geometry) != 1:
                    raise RouteFileError("Каждая метка KML должна содержать одну линию или точку")
                if _local(geometry[0].tag)[1] == "LineString":
                    lines.append((placemark, geometry[0]))
                else:
                    if len(checkpoints) >= MAX_CHECKPOINTS:
                        raise RouteFileError("На этапе допускается не более 100 контрольных точек")
                    checkpoints.append(
                        {
                            "name": _name(placemark, f"КП {len(checkpoints) + 1}"),
                            **_kml_points(geometry[0], False)[0],
                        }
                    )
            if len(lines) != 1:
                raise RouteFileError("Папка этапа должна содержать ровно одну линию LineString")
            placemark, geometry = lines[0]
            stages.append(
                budget.stage(
                    _name(container, _name(placemark, f"Этап {len(stages) + 1}")),
                    _kml_points(geometry, True),
                    checkpoints,
                )
            )
        for child in container:
            if _local(child.tag)[1] in {"Document", "Folder"}:
                visit(child)

    visit(root)
    return stages


def _gpx_coordinate(element: Element) -> dict:
    elevations = _children(element, "ele")
    elevation = (elevations[0].text or "") if elevations else None
    return _coordinate(element.get("lat"), element.get("lon"), elevation)


def _parse_gpx(root: Element, budget: _Budget) -> list[dict]:
    routes = [child for child in root if _local(child.tag)[1] in {"trk", "rte"}]
    waypoints = _children(root, "wpt")
    if waypoints and len(routes) != 1:
        raise RouteFileError("Глобальные точки GPX допустимы только при одном маршруте")
    if len(waypoints) > MAX_CHECKPOINTS:
        raise RouteFileError("На этапе допускается не более 100 контрольных точек")
    checkpoints = [
        {"name": _name(point, f"КП {i}"), **_gpx_coordinate(point)}
        for i, point in enumerate(waypoints, 1)
    ]
    stages = []
    for route in routes:
        if _local(route.tag)[1] == "trk":
            segments = _children(route, "trkseg")
            if len(segments) != 1:
                raise RouteFileError("Трек GPX должен содержать ровно один сегмент trkseg")
            elements = _children(segments[0], "trkpt")
        else:
            elements = _children(route, "rtept")
        points = []
        for element in elements:
            _append_point(points, _gpx_coordinate(element))
        stages.append(budget.stage(_name(route, f"Этап {len(stages) + 1}"), points, checkpoints))
    return stages


def parse_race_route_file(content: bytes, filename: str) -> list[dict]:
    """Прочитать гонку целиком или отклонить весь файл с русским RouteFileError

    KML: одна линия и контрольные Point в каждой папке этапа, вложенные папки
    допускаются только как контейнеры отдельных этапов без собственных меток
    GPX: каждый корневой trk или rte задаёт этап, глобальные wpt разрешены
    только для одного этапа, несколько сегментов и extensions не поддерживаются
    Стили KML и метаданные GPX читаются без выполнения ссылок или загрузок
    """
    if len(content) > MAX_RACE_ROUTE_FILE_BYTES:
        raise RouteFileError("Размер файла гонки не должен превышать 8 МиБ")
    if not content.strip():
        raise RouteFileError("Файл гонки пуст")
    extension = PurePath(filename).suffix.lower()
    if extension not in {".kml", ".gpx"}:
        raise RouteFileError("Поддерживаются только файлы KML и GPX")
    try:
        root = ElementTree.fromstring(
            content, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    except DefusedXmlException:
        raise RouteFileError("Небезопасный XML: DTD и сущности запрещены") from None
    except (ParseError, ValueError, LookupError):
        raise RouteFileError(
            "Не удалось прочитать XML: проверьте структуру и кодировку файла"
        ) from None
    namespace, name = _local(root.tag)
    if name != extension[1:]:
        raise RouteFileError("Корневой элемент XML не соответствует расширению файла")
    kml = extension == ".kml"
    if namespace not in ({"", _KML_NS} if kml else {"", *_GPX_NS}):
        raise RouteFileError("Неподдерживаемое пространство имён формата маршрута")
    _validate_tree(root, namespace, kml)
    budget = _Budget()
    stages = _parse_kml(root, budget) if kml else _parse_gpx(root, budget)
    if not stages:
        raise RouteFileError("Файл не содержит этапов с линиями маршрута")
    return stages
