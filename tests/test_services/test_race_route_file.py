"""Проверки полного импорта гонки без потери координат и высот"""

from pathlib import Path
from xml.etree import ElementTree

import pytest

KML_NS = "http://www.opengis.net/kml/2.2"
GPX_NS = "http://www.topografix.com/GPX/1/1"
REAL_FILE = Path("/Users/vladsubarev/Downloads/Берингия.Авача-2025.kml")


def parse(content, filename="race.kml"):
    # Отложенный импорт позволяет увидеть падение теста до создания сервиса
    from app.services.race_route_file import parse_race_route_file

    return parse_race_route_file(content, filename)


def kml(body, namespace=KML_NS):
    return f'<kml xmlns="{namespace}"><Document>{body}</Document></kml>'.encode()


def line(coordinates="158,53,10 159,54,20"):
    return (
        "<Placemark><name>Линия</name><LineString><coordinates>"
        f"{coordinates}</coordinates></LineString></Placemark>"
    )


def checkpoint(coordinates="158,53,10", name="КП"):
    return (
        f"<Placemark><name>{name}</name><Point><coordinates>"
        f"{coordinates}</coordinates></Point></Placemark>"
    )


def folder(body, name="Этап"):
    return f"<Folder><name>{name}</name>{body}</Folder>"


def gpx(body, namespace=GPX_NS):
    return f'<gpx xmlns="{namespace}" version="1.1" creator="test">{body}</gpx>'.encode()


def route(count=2, name="Этап"):
    points = "".join(f'<rtept lat="{i / 100000}" lon="158"/>' for i in range(count))
    return f"<rte><name>{name}</name>{points}</rte>"


def track():
    return (
        '<trk><name>Трек</name><trkseg><trkpt lat="53" lon="158"><ele>0</ele>'
        '</trkpt><trkpt lat="54" lon="159"><ele>-12.125</ele></trkpt></trkseg></trk>'
    )


def test_kml_contract_precision_and_duplicate_checkpoint_names():
    """Сохраняет контракт, точность, высоты и одноимённые контрольные точки KML"""
    result = parse(
        kml(
            folder(
                checkpoint()
                + line("158.1234567890123,53.1234567890123,0 159,54,-12.1234567890123")
                + checkpoint("159,54", "КП")
            )
        )
    )
    assert result == [
        {
            "name": "Этап",
            "points": [
                {"lat": 53.1234567890123, "lon": 158.1234567890123, "elevation": 0.0},
                {"lat": 54.0, "lon": 159.0, "elevation": -12.1234567890123},
            ],
            "checkpoints": [
                {"name": "КП", "lat": 53.0, "lon": 158.0, "elevation": 10.0},
                {"name": "КП", "lat": 54.0, "lon": 159.0, "elevation": None},
            ],
            "warnings": [],
        }
    ]
    assert all(type(p[axis]) is float for p in result[0]["points"] for axis in ("lat", "lon"))


def test_kml_stage_order_nested_folders_and_no_namespace():
    """Сохраняет порядок этапов во вложенных папках KML без пространства имён"""
    result = parse(
        kml(
            folder(folder(line("0,0 1,1"), "А") + folder(line("2,2 3,3"), "Б"), "Гонка"),
            namespace="",
        )
    )
    assert [s["name"] for s in result] == ["А", "Б"]
    assert result[0]["points"][0] == {"lat": 0.0, "lon": 0.0, "elevation": None}
    assert result[1]["checkpoints"] == []


def test_kml_single_line_without_folder():
    """Читает единственную линию KML без папки этапа"""
    assert parse(kml(line()))[0]["name"] == "Линия"


@pytest.mark.parametrize("filename", ["race.KML", "a/b/race.kml"])
def test_filename_extension(filename):
    """Принимает расширение KML в верхнем регистре и имя с путём"""
    assert len(parse(kml(folder(line())), filename)) == 1


def test_warns_about_opposite_direction_without_reversing():
    """Предупреждает об обратном направлении без перестановки линии и КП"""
    result = parse(kml(folder(checkpoint("159,54") + line() + checkpoint())))
    assert result[0]["warnings"]
    assert result[0]["points"][0]["lat"] == 53.0
    assert result[0]["checkpoints"][0]["lat"] == 54.0


def test_direction_distance_handles_antimeridian():
    """Учитывает переход через меридиан 180 градусов при проверке направления"""
    result = parse(kml(folder(checkpoint("-179.9,0") + line("179.9,0 170,0"))))
    assert result[0]["warnings"] == []


@pytest.mark.parametrize("namespace", [GPX_NS, "http://www.topografix.com/GPX/1/0", ""])
def test_gpx_track_with_global_waypoints(namespace):
    """Читает трек GPX с глобальными КП и сохраняет все значения высот"""
    result = parse(
        gpx(
            '<wpt lat="53" lon="158"><name>КП</name><ele>42.5</ele></wpt>'
            + track()
            + '<wpt lat="54" lon="159"><name>КП</name></wpt>',
            namespace,
        ),
        "race.gpx",
    )
    assert result == [
        {
            "name": "Трек",
            "points": [
                {"lat": 53.0, "lon": 158.0, "elevation": 0.0},
                {"lat": 54.0, "lon": 159.0, "elevation": -12.125},
            ],
            "checkpoints": [
                {"name": "КП", "lat": 53.0, "lon": 158.0, "elevation": 42.5},
                {"name": "КП", "lat": 54.0, "lon": 159.0, "elevation": None},
            ],
            "warnings": [],
        }
    ]


def test_gpx_independent_routes_and_tracks_without_global_waypoints():
    """Разделяет корневые маршруты и треки GPX на этапы без глобальных КП"""
    result = parse(gpx(route(name="А") + track() + route(name="Б")), "race.gpx")
    assert [s["name"] for s in result] == ["А", "Трек", "Б"]
    assert all(s["checkpoints"] == [] for s in result)
    assert result[0]["points"][0]["elevation"] is None


@pytest.mark.parametrize(
    "body",
    [
        folder(line() + line()),
        checkpoint() + folder(line()),
        folder(checkpoint()),
        folder(line() + folder(line())),
        "<Placemark><MultiGeometry><Point><coordinates>1,2</coordinates></Point>"
        "<LineString><coordinates>1,2 3,4</coordinates></LineString></MultiGeometry></Placemark>",
        "<Placemark><Polygon/></Placemark>",
        "<NetworkLink><Link><href>https://example.org</href></Link></NetworkLink>",
        "<GroundOverlay/>",
        "<Placemark><LineString><coordinates>1,2 3,4</coordinates>"
        "<coordinates>5,6 7,8</coordinates></LineString></Placemark>",
        "<Placemark><Point><coordinates>1,2 3,4</coordinates></Point></Placemark>",
        "<Placemark><name>Без геометрии</name></Placemark>" + line(),
        "<description>" + line() + "</description>",
        "<Style>" + line() + "</Style>",
        "<Folder><name>А</name><name>Б</name>" + line() + "</Folder>",
        "<Placemark>" + line() + "</Placemark>",
        "<Placemark><LineString><coordinates><name>1,2 3,4</name>"
        "</coordinates></LineString></Placemark>",
        "<Placemark><LineString><coordinates>1,2 3,4</coordinates>"
        "<Point><coordinates>1,2</coordinates></Point></LineString></Placemark>",
    ],
)
def test_rejects_ambiguous_or_unsupported_kml(body):
    """Отклоняет неоднозначные папки и неподдерживаемые структуры KML"""
    with pytest.raises(ValueError):
        parse(kml(body))


@pytest.mark.parametrize(
    "body",
    [
        route() * 2 + '<wpt lat="1" lon="2"/>',
        track() * 2 + '<wpt lat="1" lon="2"/>',
        '<trk><trkseg><trkpt lat="1" lon="2"/></trkseg>'
        '<trkseg><trkpt lat="3" lon="4"/></trkseg></trk>',
        '<trk><trkpt lat="1" lon="2"/></trk>',
        "<extensions>" + route() + "</extensions>",
        route() + '<rtept lat="1" lon="2"/>',
        route() + '<wpt lat="1" lon="2"><extensions><rte/></extensions></wpt>',
        '<rte><rtept lat="1" lon="2"><ele>1</ele><ele>2</ele></rtept>'
        '<rtept lat="3" lon="4"/></rte>',
        '<rte><rtept lon="2"/><rtept lat="3" lon="4"/></rte>',
        '<rte><rtept lat="1" lon="2"><ele/></rtept><rtept lat="3" lon="4"/></rte>',
        '<wpt lat="1" lon="2"/>',
        "<trk/>",
    ],
)
def test_rejects_ambiguous_or_unsupported_gpx(body):
    """Отклоняет неоднозначные КП, несколько сегментов и неверные структуры GPX"""
    with pytest.raises(ValueError):
        parse(gpx(body), "race.gpx")


@pytest.mark.parametrize(
    "coordinates",
    [
        "nan,53 159,54",
        "158,inf 159,54",
        "158,53,-inf 159,54",
        "181,53 159,54",
        "158,91 159,54",
        "158,-91 159,54",
        "-181,53 159,54",
        "158,53, 159,54",
        "158,53,1,2 159,54",
        "158 159,54",
        "158,53,abc 159,54",
        "158,53 158,53",
        "158,53,1 158,53,2",
        "158,53",
        "",
        "158,53 1e999,54",
        "158,53 159,54,1e999",
    ],
)
def test_rejects_invalid_kml_line_coordinates(coordinates):
    """Отклоняет неверные, неконечные и совпадающие соседние координаты KML"""
    with pytest.raises(ValueError):
        parse(kml(folder(line(coordinates))))


@pytest.mark.parametrize("coordinates", ["nan,53", "158,inf", "158,53,NaN", "181,53", "158,91"])
def test_validates_checkpoint_coordinates(coordinates):
    """Проверяет диапазоны и конечность координат и высот контрольных точек"""
    with pytest.raises(ValueError):
        parse(kml(folder(line() + checkpoint(coordinates))))


@pytest.mark.parametrize(
    "lat,lon,ele",
    [
        ("NaN", "1", "1"),
        ("1", "inf", "1"),
        ("1", "2", "nan"),
        ("91", "1", "1"),
        ("1", "181", "1"),
        ("1", "1", "1e999"),
    ],
)
def test_validates_gpx_coordinates_and_elevation(lat, lon, ele):
    """Отклоняет неконечные координаты и высоты GPX и выход за диапазоны"""
    with pytest.raises(ValueError):
        parse(
            gpx(
                f'<rte><rtept lat="{lat}" lon="{lon}"><ele>{ele}</ele></rtept>'
                '<rtept lat="3" lon="4"/></rte>'
            ),
            "race.gpx",
        )


@pytest.mark.parametrize(
    "body",
    [
        '<x:Folder xmlns:x="urn:foreign">' + line() + "</x:Folder>",
        '<description xmlns="urn:foreign">ignored</description>' + line(),
        '<Placemark><LineString><coordinates xmlns="">1,2 3,4</coordinates>'
        "</LineString></Placemark>",
        '<Folder xmlns:x="urn:foreign" x:flag="1">' + line() + "</Folder>",
    ],
)
def test_rejects_foreign_namespaces_anywhere(body):
    """Отклоняет чужие пространства имён в геометрии, метаданных и атрибутах"""
    with pytest.raises(ValueError):
        parse(kml(body))


@pytest.mark.parametrize(
    "content,filename",
    [
        (b"", "race.kml"),
        (b"   ", "race.gpx"),
        (b"<kml>", "race.kml"),
        (b"<kml/>", "race.zip"),
        (b"<gpx/>", "race.kml"),
        (b"<kml/>", "race.gpx"),
        (b'<kml xmlns="urn:foreign"/>', "race.kml"),
        (b"<kml/>", "race.kml"),
        (b"<!DOCTYPE kml><kml/>", "race.kml"),
        (b'<!DOCTYPE kml [<!ENTITY x "abc">]><kml>&x;</kml>', "race.kml"),
        (b'<!DOCTYPE kml SYSTEM "file:///etc/passwd"><kml/>', "race.kml"),
        ("<!DOCTYPE kml><kml/>".encode("utf-16"), "race.kml"),
        (b'<gpx xmlns="urn:foreign"/>', "race.gpx"),
        (gpx(route() + '<x:wpt xmlns:x="urn:foreign" lat="1" lon="2"/>'), "race.gpx"),
        (gpx('<rte><rtept lat="1" lon="2"/><rtept lat="1" lon="2"/></rte>'), "race.gpx"),
    ],
)
def test_rejects_invalid_or_unsafe_xml(content, filename):
    """Отклоняет неверный формат, повреждённый XML, DTD и сущности безопасной ошибкой"""
    with pytest.raises(ValueError) as exc:
        parse(content, filename)
    assert str(exc.value)
    assert "file:///etc/passwd" not in str(exc.value)


@pytest.mark.parametrize("count", [2001, 20000])
def test_accepts_long_lines(count):
    """Принимает линии длиннее 2000 точек вплоть до предела 20000"""
    result = parse(gpx(route(count)), "race.gpx")
    assert len(result[0]["points"]) == count


def test_rejects_line_over_limit():
    """Отклоняет линию с количеством точек больше 20000"""
    with pytest.raises(ValueError):
        parse(gpx(route(20001)), "race.gpx")


def test_total_coordinates_limit():
    """Принимает ровно 100000 координат и отклоняет превышение общего лимита"""
    assert sum(len(s["points"]) for s in parse(gpx(route(20000) * 5), "race.gpx")) == 100000
    with pytest.raises(ValueError):
        parse(gpx(route(20000) * 5 + route()), "race.gpx")


def test_stage_count_limit():
    """Принимает 32 этапа и отклоняет тридцать третий"""
    assert len(parse(kml(folder(line()) * 32))) == 32
    with pytest.raises(ValueError):
        parse(kml(folder(line()) * 33))


def test_checkpoint_count_limit():
    """Сохраняет 100 одноимённых КП и отклоняет превышение лимита на этап"""
    assert len(parse(kml(folder(line() + checkpoint() * 100)))[0]["checkpoints"]) == 100
    with pytest.raises(ValueError):
        parse(kml(folder(line() + checkpoint() * 101)))


def test_name_length_limit():
    """Принимает название из 255 символов и отклоняет более длинные названия"""
    assert parse(kml(folder(line(), "я" * 255)))[0]["name"] == "я" * 255
    for payload in [
        kml(folder(line(), "я" * 256)),
        kml(folder(line() + checkpoint(name="я" * 256))),
        gpx(route(name="я" * 256)),
    ]:
        with pytest.raises(ValueError):
            parse(payload, "race.gpx" if payload.startswith(b"<gpx") else "race.kml")


def test_file_size_limit():
    """Принимает файл ровно 8 МиБ и отклоняет превышение на один байт"""
    payload = kml(folder(line()))
    padded = payload + b" " * (8 * 1024 * 1024 - len(payload))
    assert len(parse(padded)) == 1
    with pytest.raises(ValueError):
        parse(padded + b" ")


def test_rejects_deeply_nested_xml():
    """Отклоняет XML с чрезмерной глубиной вложенности"""
    with pytest.raises(ValueError):
        parse(kml("<Folder>" * 100 + line() + "</Folder>" * 100))


@pytest.mark.skipif(not REAL_FILE.is_file(), reason="Локальный исходный KML отсутствует")
def test_real_beringia_export_preserves_every_point_and_elevation():
    """Сохраняет все этапы, координаты и высоты реального KML с предупреждением об этапе 6"""
    content = REAL_FILE.read_bytes()
    result = parse(content, REAL_FILE.name)
    assert [len(s["points"]) for s in result] == [8207, 9952, 11407, 4082, 10570, 8207]
    assert sum(len(s["points"]) for s in result) == 52425
    assert sum(len(s["checkpoints"]) for s in result) == 12
    ns = {"k": KML_NS}
    source = ElementTree.fromstring(content)
    for stage, container in zip(result, source.findall(".//k:Folder", ns), strict=True):
        assert stage["name"] == container.findtext("k:name", namespaces=ns)
        raw = container.findtext(".//k:LineString/k:coordinates", namespaces=ns).split()
        for actual, coordinate in zip(stage["points"], raw, strict=True):
            lon, lat, elevation = map(float, coordinate.split(","))
            assert actual == {"lat": lat, "lon": lon, "elevation": elevation}
        cps = [p for p in container.findall("k:Placemark", ns) if p.find("k:Point", ns) is not None]
        for actual, placemark in zip(stage["checkpoints"], cps, strict=True):
            lon, lat, elevation = map(
                float, placemark.findtext("k:Point/k:coordinates", namespaces=ns).split(",")
            )
            assert actual == {
                "name": placemark.findtext("k:name", namespaces=ns),
                "lat": lat,
                "lon": lon,
                "elevation": elevation,
            }
    assert result[5]["warnings"]
