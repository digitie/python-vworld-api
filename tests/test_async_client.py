from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlparse

import pytest

from vworld import VworldClient
from vworld.exceptions import VworldAuthError, VworldInvalidParameterError

BASE = "https://api.vworld.kr"


def _query(call) -> dict[str, list[str]]:
    return parse_qs(urlparse(str(call.request.url)).query, keep_blank_values=True)


def test_async_search_uses_httpx_and_returns_payload(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)

    async def run() -> dict:
        async with VworldClient("test-key", retry_backoff=0) as client:
            return await client.search_place("판교", size=1)

    payload = asyncio.run(run())

    assert payload == ok_payload
    query = _query(http_mock.calls[0])
    assert query["key"] == ["test-key"]
    assert query["query"] == ["판교"]
    assert query["size"] == ["1"]


def test_sync_client_aio_factory_returns_async_client(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/address", json=ok_payload)

    async def run() -> dict:
        async with VworldClient(api_key="test-key", retry_backoff=0) as client:
            return await client.geocode("판교로 242")

    payload = asyncio.run(run())

    assert payload == ok_payload
    query = _query(http_mock.calls[0])
    assert query["request"] == ["getcoord"]
    assert query["address"] == ["판교로 242"]


def test_async_data_feature_preserves_explicit_blank_domain(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/data", json=ok_payload)

    async def run() -> dict:
        client = VworldClient("test-key", domain="example.com", retry_backoff=0)
        try:
            return await client.get_data_feature("LT_C_ADEMD_INFO", domain="")
        finally:
            await client.aclose()

    asyncio.run(run())

    assert _query(http_mock.calls[0])["domain"] == [""]


def test_async_image_and_tile_fetches(http_mock):
    http_mock.add(
        "GET",
        BASE + "/req/image",
        body=b"map",
        content_type="image/png",
    )
    http_mock.add(
        "GET",
        BASE + "/req/wmts/1.0.0/test-key/Base/11/793/1746.png",
        body=b"tile",
        content_type="image/png",
    )

    async def run():
        async with VworldClient("test-key", retry_backoff=0) as client:
            static_map = await client.static_map(
                center=(126.978271, 37.566643),
                zoom=16,
                size=(128, 128),
            )
            tile = await client.get_wmts_tile("Base", 11, 793, 1746)
            return static_map, tile

    static_map, tile = asyncio.run(run())

    assert static_map.content == b"map"
    assert tile.content == b"tile"
    assert _query(http_mock.calls[0])["request"] == ["getmap"]


def test_async_validation_and_missing_key(monkeypatch):
    async def bad_search() -> None:
        client = VworldClient("test-key", retry_backoff=0)
        try:
            await client.search("판교", "address", category=None)
        finally:
            await client.aclose()

    with pytest.raises(VworldInvalidParameterError):
        asyncio.run(bad_search())

    monkeypatch.delenv("VWORLD_API_KEY", raising=False)
    monkeypatch.delenv("VWORLD_KEY", raising=False)
    with pytest.raises(VworldAuthError):
        asyncio.run(VworldClient(api_key=None).search_place("판교"))


def test_async_search_address(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)

    async def run() -> dict:
        async with VworldClient("test-key", retry_backoff=0) as client:
            return await client.search_address("성남시 분당구 판교로 242")

    payload = asyncio.run(run())

    assert payload == ok_payload
    query = _query(http_mock.calls[0])
    assert query["type"] == ["address"]
    assert query["category"] == ["road"]
    assert query["query"] == ["성남시 분당구 판교로 242"]


def test_async_search_district(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)

    async def run() -> dict:
        async with VworldClient("test-key", retry_backoff=0) as client:
            return await client.search_district("삼평동")

    payload = asyncio.run(run())

    assert payload == ok_payload
    query = _query(http_mock.calls[0])
    assert query["type"] == ["district"]
    assert query["category"] == ["L4"]


def test_async_search_road(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)

    async def run() -> dict:
        async with VworldClient("test-key", retry_backoff=0) as client:
            return await client.search_road("판교로")

    payload = asyncio.run(run())

    assert payload == ok_payload
    query = _query(http_mock.calls[0])
    assert query["type"] == ["road"]
    assert query["query"] == ["판교로"]


def test_async_reverse_geocode(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/address", json=ok_payload)

    async def run() -> dict:
        async with VworldClient("test-key", retry_backoff=0) as client:
            return await client.reverse_geocode((127.101313354, 37.402352535))

    payload = asyncio.run(run())

    assert payload == ok_payload
    query = _query(http_mock.calls[0])
    assert query["request"] == ["getaddress"]
    assert query["point"] == ["127.101313354,37.402352535"]


def test_async_reverse_geocode_latlon(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/address", json=ok_payload)

    async def run() -> dict:
        async with VworldClient("test-key", retry_backoff=0) as client:
            return await client.reverse_geocode_latlon(37.402352535, 127.101313354)

    payload = asyncio.run(run())

    assert payload == ok_payload
    query = _query(http_mock.calls[0])
    assert query["request"] == ["getaddress"]
    assert query["point"] == ["127.101313354,37.402352535"]


def test_async_get_data_feature_type(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/data", json=ok_payload)

    async def run() -> dict:
        async with VworldClient("test-key", retry_backoff=0) as client:
            return await client.get_data_feature_type("LT_C_ADEMD_INFO")

    payload = asyncio.run(run())

    assert payload == ok_payload
    query = _query(http_mock.calls[0])
    assert query["request"] == ["GetFeatureType"]
    assert query["data"] == ["LT_C_ADEMD_INFO"]


def test_async_wms_get_capabilities(http_mock):
    http_mock.add(
        "GET",
        BASE + "/req/wms",
        body="<WMS_Capabilities/>",
        content_type="text/xml",
    )

    async def run():
        async with VworldClient("test-key", retry_backoff=0) as client:
            return await client.wms_get_capabilities()

    result = asyncio.run(run())

    assert result.text == "<WMS_Capabilities/>"
    query = _query(http_mock.calls[0])
    assert query["SERVICE"] == ["WMS"]
    assert query["REQUEST"] == ["GetCapabilities"]


def test_async_wfs_get_feature(http_mock):
    http_mock.add(
        "GET",
        BASE + "/req/wfs",
        body="<wfs:FeatureCollection/>",
        content_type="text/xml",
    )

    async def run():
        async with VworldClient("test-key", retry_backoff=0) as client:
            return await client.wfs_get_feature("lt_c_landinfobasemap")

    result = asyncio.run(run())

    assert result.text == "<wfs:FeatureCollection/>"
    query = _query(http_mock.calls[0])
    assert query["SERVICE"] == ["WFS"]
    assert query["REQUEST"] == ["GetFeature"]
    assert query["TYPENAME"] == ["lt_c_landinfobasemap"]
