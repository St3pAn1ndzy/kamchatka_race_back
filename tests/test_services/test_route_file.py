import pytest

from app.schemas.admin_stage_route import StageRouteReplaceRequest
from app.services.route_file import MAX_ROUTE_FILE_BYTES, RouteFileError, parse_route_file

KML_NS = "http://www.opengis.net/kml/2.2"
GPX_NS = "http://www.topografix.com/GPX/1/1"


def _kml(body: str, namespace: str = KML_NS) -> bytes:
    return f'<kml xmlns="{namespace}"><Document>{body}</Document></kml>'.encode()


def _line(coordinates: str = "158,53,100 159,54,200") -> str:
    return (
        f"<Placemark><LineString><coordinates>{coordinates}</coordinates></LineString></Placemark>"
    )


def _gpx(body: str, namespace: str = GPX_NS) -> bytes:
    return f'<gpx xmlns="{namespace}">{body}</gpx>'.encode()


def _track(points: str = '<trkpt lat="53" lon="158"/><trkpt lat="54" lon="159"/>') -> str:
    return f"<trk><trkseg>{points}</trkseg></trk>"


def _route() -> str:
    return '<rte><rtept lat="53" lon="158"/><rtept lat="54" lon="159"/></rte>'


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (_kml(_line()), "маршрут.KmL"),
        (_gpx(_track()), "маршрут.GPX"),
        (_gpx(_route()), "маршрут.gpx"),
        (_gpx(_track(), "http://www.topografix.com/GPX/1/0"), "route.gpx"),
        (_kml(_line(), ""), "route.kml"),
        (_gpx(_track(), ""), "route.gpx"),
        (_gpx(_route(), ""), "route.gpx"),
    ],
)
def test_valid_route_preserves_order(content: bytes, filename: str) -> None:
    """Оба формата сохраняют порядок и возвращают схему замены маршрута"""
    result = parse_route_file(content, filename)

    assert isinstance(result, StageRouteReplaceRequest)
    assert result.model_dump() == {
        "points": [{"lat": 53.0, "lon": 158.0}, {"lat": 54.0, "lon": 159.0}]
    }


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (_kml(_line("-180,-90,ignored\n\t180,90")), "route.kml"),
        (
            _gpx(
                _track(
                    '<trkpt lat="-90" lon="-180"><ele>ignored</ele></trkpt>'
                    '<trkpt lat="90" lon="180"><ele>NaN</ele></trkpt>'
                )
            ),
            "route.gpx",
        ),
    ],
)
def test_altitude_is_ignored_and_boundaries_are_valid(content: bytes, filename: str) -> None:
    """Высота не импортируется и предельные широта и долгота разрешены"""
    assert parse_route_file(content, filename).model_dump() == {
        "points": [{"lat": -90.0, "lon": -180.0}, {"lat": 90.0, "lon": 180.0}]
    }


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (_kml("<Placemark><Point><coordinates>1,2</coordinates></Point></Placemark>"), "a.kml"),
        (_gpx('<wpt lat="1" lon="2"/><wpt lat="3" lon="4"/>'), "a.gpx"),
    ],
)
def test_markers_do_not_form_a_route(content: bytes, filename: str) -> None:
    """Одиночные метки не превращаются в линию маршрута"""
    with pytest.raises(RouteFileError, match="маршрут|лини"):
        parse_route_file(content, filename)


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (
            _kml("<Placemark><Point><coordinates>0,0</coordinates></Point></Placemark>" + _line()),
            "a.kml",
        ),
        (_gpx('<wpt lat="0" lon="0"/>' + _track()), "a.gpx"),
    ],
)
def test_markers_alongside_route_are_ignored(content: bytes, filename: str) -> None:
    """Метки рядом с маршрутом не добавляют точки в результат"""
    assert len(parse_route_file(content, filename).points) == 2


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (_kml(_line() + _line()), "a.kml"),
        (
            _kml(
                "<Placemark><MultiGeometry><LineString/><LineString/></MultiGeometry></Placemark>"
            ),
            "a.kml",
        ),
        (_gpx(_track() + _track()), "a.gpx"),
        (_gpx(_route() + _route()), "a.gpx"),
        (_gpx(_track() + _route()), "a.gpx"),
        (_gpx("<trk><trkseg/><trkseg/></trk>"), "a.gpx"),
    ],
)
def test_ambiguous_routes_are_rejected(content: bytes, filename: str) -> None:
    """Несколько линий маршрутов или сегментов отклоняются без склейки"""
    with pytest.raises(RouteFileError, match="ровно од|несколько"):
        parse_route_file(content, filename)


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (_kml(_line(), "urn:foreign"), "a.kml"),
        (_gpx(_track(), "urn:foreign"), "a.gpx"),
        (_kml(_line(), "http://earth.google.com/kml/2.0"), "a.kml"),
        (_gpx(_track(), "http://www.topografix.com/GPX/2/0"), "a.gpx"),
        (_kml(_line().replace("<LineString>", '<LineString xmlns="urn:foreign">')), "a.kml"),
        (_gpx(_track().replace("<trkseg>", '<trkseg xmlns="">')), "a.gpx"),
    ],
)
def test_unsupported_or_mixed_namespaces_are_rejected(content: bytes, filename: str) -> None:
    """Чужие и смешанные пространства имён не принимаются за маршрут"""
    with pytest.raises(RouteFileError):
        parse_route_file(content, filename)


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (_gpx("<extensions>" + _track() + "</extensions>", ""), "a.gpx"),
        (_gpx("<trk><extensions><trkseg/></extensions></trk>", ""), "a.gpx"),
        (_gpx('<rte><extensions><rtept lat="1" lon="2"/></extensions></rte>', ""), "a.gpx"),
        (_kml("<extensions>" + _line() + "</extensions>", ""), "a.kml"),
        (
            _kml(
                _line()
                .replace("<coordinates>", "<extensions><coordinates>")
                .replace("</coordinates>", "</coordinates></extensions>"),
                "",
            ),
            "a.kml",
        ),
    ],
)
def test_namespace_free_structure_is_restricted(content: bytes, filename: str) -> None:
    """Без пространства имён принимается только явная структура формата"""
    with pytest.raises(RouteFileError):
        parse_route_file(content, filename)


@pytest.mark.parametrize("content", [b"<kml>", b"not XML", b"<kml/><kml/>", b"<kml>\xff</kml>"])
def test_malformed_xml_is_rejected(content: bytes) -> None:
    """Повреждённый XML и неверная кодировка возвращают безопасную ошибку"""
    with pytest.raises(RouteFileError, match="XML"):
        parse_route_file(content, "route.kml")


@pytest.mark.parametrize(
    "declaration",
    [
        "<!DOCTYPE kml>",
        '<!DOCTYPE kml [<!ENTITY secret "secret-content">]>',
        '<!DOCTYPE kml SYSTEM "file:///etc/passwd">',
        '<!DOCTYPE kml [<!ENTITY secret SYSTEM "file:///etc/passwd">]>',
    ],
)
def test_dtd_and_entities_are_forbidden(declaration: str) -> None:
    """Любой DTD включая внешние сущности запрещён до извлечения координат"""
    with pytest.raises(RouteFileError, match="XML|DTD") as error:
        parse_route_file(declaration.encode() + _kml(_line()), "route.kml")
    assert "secret-content" not in str(error.value)
    assert "file:///etc/passwd" not in str(error.value)


def test_utf8_names_and_xml_declaration_are_supported() -> None:
    """Русское имя файла и текст XML в UTF-8 не мешают импорту"""
    content = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>' + _kml(
        "<name>Камчатка &amp; гонка</name>" + _line()
    )
    assert len(parse_route_file(content, "Трасса.kml").points) == 2


@pytest.mark.parametrize("value", ["secret-content", "NaN", "inf", "-Infinity", "1e999", "181"])
@pytest.mark.parametrize("format_name", ["kml", "gpx"])
def test_invalid_longitude_is_rejected_safely(value: str, format_name: str) -> None:
    """Неверная бесконечная и выходящая за диапазон долгота не раскрывается в ошибке"""
    content = (
        _kml(_line(f"{value},53 159,54"))
        if format_name == "kml"
        else _gpx(_track(f'<trkpt lat="53" lon="{value}"/><trkpt lat="54" lon="159"/>'))
    )
    with pytest.raises(RouteFileError, match="[Кк]оординат|точ|маршрут") as error:
        parse_route_file(content, f"route.{format_name}")
    assert "secret-content" not in str(error.value)


@pytest.mark.parametrize("value", ["NaN", "-91", "91", "oops", "Infinity"])
@pytest.mark.parametrize("format_name", ["kml", "gpx"])
def test_invalid_latitude_is_rejected(value: str, format_name: str) -> None:
    """Широта проходит проверку числа конечности и допустимого диапазона"""
    content = (
        _kml(_line(f"158,{value} 159,54"))
        if format_name == "kml"
        else _gpx(_track(f'<trkpt lat="{value}" lon="158"/><trkpt lat="54" lon="159"/>'))
    )
    with pytest.raises(RouteFileError):
        parse_route_file(content, f"route.{format_name}")


@pytest.mark.parametrize("coordinates", ["158", "158,,1 159,54", "158,53,1,2 159,54", "", "158,53"])
def test_invalid_kml_coordinate_tuples_are_rejected(coordinates: str) -> None:
    """Неполные лишние и пустые координаты KML отклоняются"""
    with pytest.raises(RouteFileError):
        parse_route_file(_kml(_line(coordinates)), "route.kml")


@pytest.mark.parametrize(
    "body",
    ["<trk/>", "<rte/>", "<trk><trkseg/></trk>", '<trk><trkseg><trkpt lat="53"/></trkseg></trk>'],
)
def test_missing_gpx_segments_or_coordinates_are_rejected(body: str) -> None:
    """Пустые сегменты и точки GPX без обязательных атрибутов отклоняются"""
    with pytest.raises(RouteFileError):
        parse_route_file(_gpx(body), "route.gpx")


@pytest.mark.parametrize("content", [b"", b" \t\r\n"])
def test_empty_file_is_rejected(content: bytes) -> None:
    """Пустой файл отклоняется до разбора XML"""
    with pytest.raises(RouteFileError, match="пуст"):
        parse_route_file(content, "route.kml")


def test_file_size_limit_is_enforced_before_xml_parsing() -> None:
    """Файл больше двух МиБ отклоняется по размеру до разбора XML"""
    with pytest.raises(RouteFileError, match="размер|МБ|МиБ"):
        parse_route_file(b"!" * (2 * 1024 * 1024 + 1), "route.kml")
    assert MAX_ROUTE_FILE_BYTES == 2 * 1024 * 1024


def test_file_at_size_limit_is_accepted() -> None:
    """Корректный XML размером ровно два МиБ принимается"""
    content = _kml(_line())
    content += b" " * (2 * 1024 * 1024 - len(content))
    assert len(parse_route_file(content, "route.kml").points) == 2


@pytest.mark.parametrize("count", [0, 1, 2000, 2001])
@pytest.mark.parametrize("format_name", ["kml", "gpx"])
def test_point_count_limits(count: int, format_name: str) -> None:
    """Импорт соблюдает нижнюю и верхнюю границы числа точек схемы"""
    content = (
        _kml(_line(" ".join(f"{i / 100},53" for i in range(count))))
        if format_name == "kml"
        else _gpx(_track("".join(f'<trkpt lat="53" lon="{i / 100}"/>' for i in range(count))))
    )
    if count == 2000:
        assert len(parse_route_file(content, f"route.{format_name}").points) == 2000
    else:
        with pytest.raises(RouteFileError):
            parse_route_file(content, f"route.{format_name}")


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (_kml(_line("158,53,1 158,53,2")), "a.kml"),
        (_gpx(_track('<trkpt lat="53" lon="158"/><trkpt lat="53.0" lon="158.0"/>')), "a.gpx"),
    ],
)
def test_adjacent_duplicate_points_are_rejected(content: bytes, filename: str) -> None:
    """Повтор соседних координат запрещён независимо от высоты и записи числа"""
    with pytest.raises(RouteFileError, match="[Сс]осед"):
        parse_route_file(content, filename)


def test_nonadjacent_duplicate_points_are_allowed() -> None:
    """Замкнутый маршрут сохраняет совпадающие несоседние точки"""
    assert len(parse_route_file(_kml(_line("1,2 3,4 1,2")), "route.kml").points) == 3


@pytest.mark.parametrize("filename", ["route", "route.xml", "route.kml.exe", "", "route.gpx "])
def test_unsupported_extension_is_rejected_before_xml(filename: str) -> None:
    """Неподдерживаемое расширение отклоняется до разбора XML"""
    with pytest.raises(RouteFileError, match="расширен|формат|KML|GPX"):
        parse_route_file(b"invalid XML", filename)


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (_kml(_line()), "route.gpx"),
        (_gpx(_track()), "route.kml"),
        (b"<Document/>", "route.kml"),
        (b"<trk/>", "route.gpx"),
    ],
)
def test_root_must_match_extension(content: bytes, filename: str) -> None:
    """Корневой элемент должен соответствовать расширению файла"""
    with pytest.raises(RouteFileError, match="кор|формат|расширен"):
        parse_route_file(content, filename)


@pytest.mark.parametrize(
    "body",
    [
        "<Placemark><LineString/></Placemark>",
        "<Placemark><LineString><coordinates>1,2 3,4</coordinates>"
        "<coordinates>5,6 7,8</coordinates></LineString></Placemark>",
        "<Placemark><LineString><coordinates>1,2 <extra/>3,4</coordinates>"
        "</LineString></Placemark>",
    ],
)
def test_kml_requires_one_plain_coordinates_element(body: str) -> None:
    """Линия KML требует единственный текстовый элемент координат"""
    with pytest.raises(RouteFileError):
        parse_route_file(_kml(body), "route.kml")


def test_prefixed_namespace_and_nested_kml_containers() -> None:
    """Префикс пространства имён и штатные вложенные контейнеры KML поддерживаются"""
    content = (
        f'<k:kml xmlns:k="{KML_NS}"><k:Document><k:Folder><k:Placemark>'
        "<k:MultiGeometry><k:LineString><k:coordinates>158,53 159,54</k:coordinates>"
        "</k:LineString></k:MultiGeometry></k:Placemark></k:Folder></k:Document></k:kml>"
    ).encode()
    assert len(parse_route_file(content, "route.kml").points) == 2


@pytest.mark.parametrize("format_name", ["kml", "gpx"])
def test_unsupported_xml_encoding_is_reported_safely(format_name: str) -> None:
    """Неизвестная кодировка XML преобразуется в человеческую ошибку"""
    with pytest.raises(RouteFileError, match="XML"):
        parse_route_file(
            b'<?xml version="1.0" encoding="secret-content"?><kml/>',
            f"route.{format_name}",
        )


def test_nested_gpx_cannot_hide_an_extra_route() -> None:
    """Вложенный корень GPX не скрывает дополнительный маршрут от проверки неоднозначности"""
    content = _gpx(_track() + "<extensions><gpx>" + _route() + "</gpx></extensions>")
    with pytest.raises(RouteFileError):
        parse_route_file(content, "route.gpx")
