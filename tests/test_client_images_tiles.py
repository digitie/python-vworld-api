from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from vworld import TileLayer
from vworld.exceptions import VworldInvalidParameterError

BASE = "https://api.vworld.kr"


def _query(call) -> dict[str, list[str]]:
    return parse_qs(urlparse(str(call.request.url)).query)


async def test_legend_graphic_params(client, http_mock):
    http_mock.add("GET", BASE + "/req/image", body=b"legend", content_type="image/png")

    response = await client.get_legend_graphic("lt_c_uq111", style="lt_c_uq111", type="layer")

    assert response.content == b"legend"
    query = _query(http_mock.calls[0])
    assert query["service"] == ["image"]
    assert query["request"] == ["GetLegendGraphic"]
    assert query["version"] == ["2.0"]
    assert query["layer"] == ["lt_c_uq111"]
    assert query["style"] == ["lt_c_uq111"]
    assert query["type"] == ["LAYER"]


async def test_static_map_params_repeat_marker_and_route(client, http_mock):
    http_mock.add("GET", BASE + "/req/image", body=b"map", content_type="image/png")

    response = await client.static_map(
        center=(126.978271, 37.566643),
        zoom=16,
        size=(400, 400),
        marker=["point:126.978271 37.566643|image:img01", "point:127 37|image:img02"],
        route=["point:126 37,127 38|color:red|width:2"],
        layers=["lt_c_uq111", "lt_c_uq112"],
        styles=["s1", "s2"],
    )

    assert response.content == b"map"
    query = _query(http_mock.calls[0])
    assert query["request"] == ["getmap"]
    assert query["center"] == ["126.978271,37.566643"]
    assert query["zoom"] == ["16"]
    assert query["size"] == ["400,400"]
    assert query["layers"] == ["lt_c_uq111,lt_c_uq112"]
    assert query["styles"] == ["s1,s2"]
    assert query["marker"] == [
        "point:126.978271 37.566643|image:img01",
        "point:127 37|image:img02",
    ]
    assert query["route"] == ["point:126 37,127 38|color:red|width:2"]


def test_image_url_builders(client):
    assert "request=GetLegendGraphic" in client.legend_graphic_url("lt_c_uq111")
    assert "request=GetLegendStyle" in client.legend_style_url("lt_c_uq111")
    assert "request=getmap" in client.static_map_url(center=(1, 2), zoom=10, size=(100, 100))
    assert "service=search" in client.build_rest_url("/req/search", {"service": "search"})


def test_wmts_and_tms_url_builders(client):
    assert client.wmts_tile_url(TileLayer.BASE, 11, 793, 1746) == (
        "https://api.vworld.kr/req/wmts/1.0.0/test-key/Base/11/793/1746.png"
    )
    assert client.wmts_tile_url("Satellite", 11, 793, 1746) == (
        "https://api.vworld.kr/req/wmts/1.0.0/test-key/Satellite/11/793/1746.jpeg"
    )
    assert client.tms_tile_url("white", 18, 1, 2) == (
        "https://api.vworld.kr/req/tms/1.0.0/test-key/white/18/1/2.png"
    )
    assert client.wmts_capabilities_url() == (
        "https://api.vworld.kr/req/wmts/1.0.0/test-key/WMTSCapabilities.xml"
    )
    assert client.tms_resource_url() == "https://api.vworld.kr/req/tms/1.0.0/test-key"


def test_theme_tile_urls_allow_png_for_satellite_themes(client):
    assert client.wmts_theme_tile_url("cities", 2025, "Oslo", 11, 1086, 596) == (
        "https://api.vworld.kr/req/wmts/1.0.0/test-key/Satellite/themes/cities/2025/"
        "Oslo/11/1086/596.png"
    )
    assert client.tms_theme_tile_url("cities", 2025, "Oslo", 11, 1086, 596) == (
        "https://api.vworld.kr/req/tms/1.0.0/test-key/Satellite/themes/cities/2025/"
        "Oslo/11/1086/596.png"
    )


async def test_fetch_tiles_do_not_add_query_key(client, http_mock):
    url = "https://api.vworld.kr/req/wmts/1.0.0/test-key/Base/11/793/1746.png"
    http_mock.add("GET", url, body=b"tile", content_type="image/png")

    response = await client.get_wmts_tile("Base", 11, 793, 1746)

    assert response.content == b"tile"
    assert str(http_mock.calls[0].request.url) == url


async def test_fetch_tms_resource_text(client, http_mock):
    url = "https://api.vworld.kr/req/tms/1.0.0/test-key"
    http_mock.add("GET", url, body="<TileMapService/>", content_type="text/xml")

    response = await client.get_tms_resource()

    assert response.text == "<TileMapService/>"
    assert str(http_mock.calls[0].request.url) == url


async def test_fetch_more_tile_and_text_helpers(client, http_mock):
    urls = [
        "https://api.vworld.kr/req/wmts/1.0.0/test-key/WMTSCapabilities.xml",
        "https://api.vworld.kr/req/wmts/1.0.0/test-key/Satellite/themes/cities/2025/Oslo/11/1086/596.png",
        "https://api.vworld.kr/req/tms/1.0.0/test-key/Base/11/793/1746.png",
        "https://api.vworld.kr/req/tms/1.0.0/test-key/Satellite/themes/cities/2025/Oslo/11/1086/596.png",
    ]
    http_mock.add("GET", urls[0], body="<Capabilities/>", content_type="text/xml")
    for url in urls[1:]:
        http_mock.add("GET", url, body=b"tile", content_type="image/png")

    assert (await client.get_wmts_capabilities()).text == "<Capabilities/>"
    assert (
        await client.get_wmts_theme_tile("cities", 2025, "Oslo", 11, 1086, 596)
    ).content == b"tile"
    assert (await client.get_tms_tile("Base", 11, 793, 1746)).content == b"tile"
    assert (
        await client.get_tms_theme_tile("cities", 2025, "Oslo", 11, 1086, 596)
    ).content == b"tile"


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.wmts_tile_url("Base", 5, 0, 0),
        lambda c: c.wmts_tile_url("white", 19, 0, 0),
        lambda c: c.wmts_tile_url("Satellite", 11, 0, 0, tile_type="png"),
        lambda c: c.wmts_tile_url("bad", 11, 0, 0),
        lambda c: c.tms_tile_url("Base", 11, -1, 0),
        lambda c: c.static_map_url(center=(1, 2), zoom=19, size=(100, 100)),
        lambda c: c.static_map_url(center=(1, 2), zoom=10, size=(1025, 100)),
        lambda c: c.legend_graphic_url("lt_c_uq111", type="bad"),
    ],
)
def test_tile_and_image_validation(client, call):
    with pytest.raises(VworldInvalidParameterError):
        call(client)
