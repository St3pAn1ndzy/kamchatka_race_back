"""Безопасное чтение единственной линии маршрута из KML или GPX"""

from pathlib import PurePath
from xml.etree.ElementTree import Element, ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pydantic import ValidationError

from app.schemas.admin_stage_route import StageRouteReplaceRequest

MAX_ROUTE_FILE_BYTES = 2 * 1024 * 1024

_KML_NAMESPACE = "http://www.opengis.net/kml/2.2"
_GPX_NAMESPACES = {"http://www.topografix.com/GPX/1/0", "http://www.topografix.com/GPX/1/1"}


class RouteFileError(ValueError):
    """Ошибка импорта файла маршрута"""


def _split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        namespace, name = tag[1:].split("}", 1)
        return namespace, name
    return "", tag


def _tag(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}" if namespace else name


def _check_namespaces(root: Element, namespace: str, names: set[str]) -> None:
    for element in root.iter():
        element_namespace, name = _split_tag(element.tag)
        if name in names and element_namespace != namespace:
            raise RouteFileError("Элементы маршрута используют несовместимые пространства имён")


def _parse_kml(root: Element, namespace: str) -> list[dict[str, float]]:
    _check_namespaces(root, namespace, {"LineString", "coordinates"})
    lines = list(root.iter(_tag(namespace, "LineString")))
    if len(lines) != 1:
        raise RouteFileError("Файл KML должен содержать ровно одну линию маршрута LineString")

    parents = {child: parent for parent in root.iter() for child in parent}
    containers = {
        _tag(namespace, name) for name in ("Document", "Folder", "Placemark", "MultiGeometry")
    }
    parent = parents[lines[0]]
    while parent is not root:
        if parent.tag not in containers:
            raise RouteFileError("Неподдерживаемая структура линии маршрута KML")
        parent = parents[parent]

    coordinates = lines[0].findall(_tag(namespace, "coordinates"))
    if len(coordinates) != 1 or len(coordinates[0]):
        raise RouteFileError("Линия KML должна содержать один текстовый элемент координат")

    points = []
    for coordinate in (coordinates[0].text or "").split():
        values = coordinate.split(",")
        if len(values) not in (2, 3):
            raise RouteFileError("Координаты KML должны иметь вид долгота,широта[,высота]")
        try:
            points.append({"lat": float(values[1]), "lon": float(values[0])})
        except ValueError:
            raise RouteFileError("Координаты маршрута должны быть числами") from None
    return points


def _parse_gpx(root: Element, namespace: str) -> list[dict[str, float]]:
    expected_parents = {
        "trk": "gpx",
        "rte": "gpx",
        "trkseg": "trk",
        "trkpt": "trkseg",
        "rtept": "rte",
    }
    _check_namespaces(root, namespace, set(expected_parents))
    parents = {child: parent for parent in root.iter() for child in parent}
    for element, parent in parents.items():
        _, name = _split_tag(element.tag)
        if name in expected_parents and parent.tag != _tag(namespace, expected_parents[name]):
            raise RouteFileError("Неподдерживаемая структура маршрута GPX")
        if name in {"trk", "rte"} and parent is not root:
            raise RouteFileError(
                "Маршрут GPX должен находиться непосредственно в корневом элементе"
            )

    tracks = root.findall(_tag(namespace, "trk"))
    routes = root.findall(_tag(namespace, "rte"))
    if len(tracks) + len(routes) != 1:
        raise RouteFileError("Файл GPX должен содержать ровно один маршрут trk или rte")

    if tracks:
        segments = tracks[0].findall(_tag(namespace, "trkseg"))
        if len(segments) != 1:
            raise RouteFileError("Маршрут GPX должен содержать ровно один сегмент trkseg")
        elements = segments[0].findall(_tag(namespace, "trkpt"))
    else:
        elements = routes[0].findall(_tag(namespace, "rtept"))

    points = []
    for element in elements:
        try:
            points.append(
                {"lat": float(element.attrib["lat"]), "lon": float(element.attrib["lon"])}
            )
        except (KeyError, ValueError):
            raise RouteFileError(
                "Каждая точка GPX должна содержать числовые широту и долготу"
            ) from None
    return points


def parse_route_file(content: bytes, filename: str) -> StageRouteReplaceRequest:
    """Преобразовать файл в запрос замены маршрута"""
    if len(content) > MAX_ROUTE_FILE_BYTES:
        raise RouteFileError("Размер файла маршрута не должен превышать 2 МиБ")
    if not content.strip():
        raise RouteFileError("Файл маршрута пуст")
    extension = PurePath(filename).suffix.lower()
    if extension not in {".kml", ".gpx"}:
        raise RouteFileError("Поддерживаются только файлы с расширением KML или GPX")

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

    namespace, name = _split_tag(root.tag)
    if name != extension[1:]:
        raise RouteFileError("Корневой элемент XML не соответствует расширению файла")
    supported_namespaces = {_KML_NAMESPACE, ""} if extension == ".kml" else _GPX_NAMESPACES | {""}
    if namespace not in supported_namespaces:
        raise RouteFileError("Неподдерживаемое пространство имён формата маршрута")

    points = _parse_kml(root, namespace) if extension == ".kml" else _parse_gpx(root, namespace)
    try:
        return StageRouteReplaceRequest.model_validate({"points": points})
    except ValidationError as error:
        # Не включаем входные данные и диагностический текст XML в ответ пользователю
        errors = error.errors(include_input=False, include_context=False, include_url=False)
        if any(item["type"] in {"too_short", "too_long"} for item in errors):
            message = "Маршрут должен содержать от 2 до 2000 точек"
        elif any(item["type"] == "value_error" for item in errors):
            message = "Соседние точки маршрута не должны совпадать"
        else:
            message = (
                "Координаты должны быть конечными числами: "
                "широта от -90 до 90, долгота от -180 до 180"
            )
        raise RouteFileError(message) from None
