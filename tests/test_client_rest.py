from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from vworld import VworldClient
from vworld.exceptions import VworldAuthError, VworldInvalidParameterError

BASE = "https://api.vworld.kr"


def _query(call) -> dict[str, list[str]]:
    return parse_qs(urlparse(str(call.request.url)).query, keep_blank_values=True)


async def test_search_place_query_params(client, ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)

    (
        await client.search_place(
            "공간정보산업진흥원",
            size=20,
            page=2,
            bbox=(14140071.146077, 4494339.6527027, 14160071.146077, 4496339.6527027),
            crs="EPSG:900913",
        )
    )

    query = _query(http_mock.calls[0])
    assert query["service"] == ["search"]
    assert query["request"] == ["search"]
    assert query["version"] == ["2.0"]
    assert query["type"] == ["place"]
    assert query["query"] == ["공간정보산업진흥원"]
    assert query["size"] == ["20"]
    assert query["page"] == ["2"]
    assert "14140071.146077" in query["bbox"][0]
    assert "1.0" not in str(http_mock.calls[0].request.url)


async def test_search_requires_category_for_address_and_district(client):
    with pytest.raises(VworldInvalidParameterError):
        (await client.search("판교로 242", "address", category=None))

    with pytest.raises(VworldInvalidParameterError):
        (await client.search("삼평동", "district", category=None))


async def test_search_more_helpers_and_validation(client, monkeypatch):
    monkeypatch.setenv("VWORLD_API_KEY", " env-\nkey\t")
    assert VworldClient.from_env().api_key == "env-key"

    with pytest.raises(VworldInvalidParameterError):
        (await client.search("", "place"))
    with pytest.raises(VworldInvalidParameterError):
        (await client.search("판교", "unknown"))
    with pytest.raises(VworldInvalidParameterError):
        (await client.geocode("", type="road"))
    with pytest.raises(VworldInvalidParameterError):
        (await client.geocode("판교로 242", type="both"))
    with pytest.raises(VworldInvalidParameterError):
        (await client.reverse_geocode((127, 37), type="unknown"))
    with pytest.raises(VworldInvalidParameterError):
        (await client.get_data_feature(""))
    with pytest.raises(VworldInvalidParameterError):
        (await client.get_data_feature_type(""))


def test_from_env_file_loads_key_and_domain(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'VWORLD_API_KEY=" file-\tkey "\nVWORLD_DOMAIN=example.com\n# ignored\n',
        encoding="utf-8",
    )

    client = VworldClient.from_env_file(env_file)

    assert client.api_key == "file-key"
    assert client.domain == "example.com"


async def test_pasted_api_key_whitespace_is_removed(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)

    client = VworldClient(" test-\nkey\t", retry_backoff=0)
    (await client.search_place("판교"))

    query = _query(http_mock.calls[0])
    assert client.api_key == "test-key"
    assert query["key"] == ["test-key"]


def test_explicit_blank_domain_is_preserved(monkeypatch):
    monkeypatch.setenv("VWORLD_DOMAIN", "example.com")

    client = VworldClient("test-key", domain="")

    assert client.domain == ""


async def test_blank_client_domain_suppresses_env_domain(monkeypatch, ok_payload, http_mock):
    monkeypatch.setenv("VWORLD_DOMAIN", "example.com")
    http_mock.add("GET", BASE + "/req/data", json=ok_payload)

    client = VworldClient("test-key", domain="")
    (await client.get_data_feature("LT_C_ADEMD_INFO"))

    assert "domain" not in _query(http_mock.calls[0])


async def test_search_address_helper_adds_default_category(client, ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)

    (await client.search_address("성남시 분당구 판교로 242"))

    query = _query(http_mock.calls[0])
    assert query["type"] == ["address"]
    assert query["category"] == ["road"]


async def test_geocode_query_params(client, ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/address", json=ok_payload)

    (await client.geocode("판교로 242", type="road", refine=False, simple=True))

    query = _query(http_mock.calls[0])
    assert query["service"] == ["address"]
    assert query["request"] == ["getcoord"]
    assert query["version"] == ["2.0"]
    assert query["address"] == ["판교로 242"]
    assert query["type"] == ["road"]
    assert query["refine"] == ["false"]
    assert query["simple"] == ["true"]


async def test_reverse_geocode_query_params(client, ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/address", json=ok_payload)

    (await client.reverse_geocode((127.101313354, 37.402352535), type="both", zipcode=False))

    query = _query(http_mock.calls[0])
    assert query["request"] == ["getaddress"]
    assert query["point"] == ["127.101313354,37.402352535"]
    assert query["type"] == ["both"]
    assert query["zipcode"] == ["false"]


async def test_data_feature_query_params_and_domain(client, ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/data", json=ok_payload)

    (
        await client.get_data_feature(
            "LT_C_ADEMD_INFO",
            attr_filter=["emd_cd:=:11650108", "emd_kor_nm:like:서초"],
            columns=["emd_cd", "full_nm"],
            geometry=False,
            attribute=True,
            buffer=10,
            domain="example.com",
        )
    )

    query = _query(http_mock.calls[0])
    assert query["service"] == ["data"]
    assert query["request"] == ["GetFeature"]
    assert query["data"] == ["LT_C_ADEMD_INFO"]
    assert query["attrFilter"] == ["emd_cd:=:11650108|emd_kor_nm:like:서초"]
    assert query["columns"] == ["emd_cd,full_nm"]
    assert query["geometry"] == ["false"]
    assert query["attribute"] == ["true"]
    assert query["buffer"] == ["10"]
    assert query["domain"] == ["example.com"]


async def test_data_feature_accepts_explicit_blank_domain(client, ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/data", json=ok_payload)

    (await client.get_data_feature("LT_C_ADEMD_INFO", domain=""))

    assert _query(http_mock.calls[0])["domain"] == [""]


async def test_data_feature_type_query_params(client, ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/data", json=ok_payload)

    (await client.get_data_feature_type("LT_C_ADEMD_INFO"))

    query = _query(http_mock.calls[0])
    assert query["request"] == ["GetFeatureType"]
    assert query["version"] == ["2.0"]


async def test_missing_key_raises_before_network(monkeypatch):
    monkeypatch.delenv("VWORLD_API_KEY", raising=False)
    monkeypatch.delenv("VWORLD_KEY", raising=False)
    with pytest.raises(VworldAuthError):
        (await VworldClient(api_key=None).search_place("판교"))


async def test_search_district_and_road_helpers(client, ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)

    (await client.search_district("삼평동"))
    (await client.search_road("판교로"))

    assert _query(http_mock.calls[0])["type"] == ["district"]
    assert _query(http_mock.calls[0])["category"] == ["L4"]
    assert _query(http_mock.calls[1])["type"] == ["road"]


async def test_iter_search_items_follows_pages_and_caps_items(client, http_mock):
    http_mock.add(
        "GET",
        BASE + "/req/search",
        json={
            "response": {
                "status": "OK",
                "record": {"total": "4", "current": "2"},
                "page": {"total": "2", "current": "1", "size": "2"},
                "result": {"items": [{"id": "1"}, {"id": "2"}]},
            }
        },
    )
    http_mock.add(
        "GET",
        BASE + "/req/search",
        json={
            "response": {
                "status": "OK",
                "record": {"total": "4", "current": "2"},
                "page": {"total": "2", "current": "2", "size": "2"},
                "result": {"items": [{"id": "3"}, {"id": "4"}]},
            }
        },
    )

    items = [item async for item in client.iter_search_items("판교", "place", size=2, max_items=3)]

    assert [item["id"] for item in items] == ["1", "2", "3"]
    assert _query(http_mock.calls[0])["page"] == ["1"]
    assert _query(http_mock.calls[1])["page"] == ["2"]


async def test_iter_data_feature_pages_preserves_request_params(client, http_mock):
    http_mock.add(
        "GET",
        BASE + "/req/data",
        json={
            "response": {
                "status": "OK",
                "record": {"total": "1", "current": "1"},
                "page": {"total": "1", "current": "3", "size": "1"},
                "result": {"items": [{"id": "feature"}]},
            }
        },
    )

    pages = [
        item
        async for item in client.iter_data_feature_pages(
            "LT_C_ADEMD_INFO",
            attr_filter=["emd_cd:=:11650108"],
            columns=["emd_cd"],
            geometry=False,
            size=1,
            start_page=3,
            domain="",
        )
    ]

    assert pages[0]["response"]["status"] == "OK"
    query = _query(http_mock.calls[0])
    assert query["data"] == ["LT_C_ADEMD_INFO"]
    assert query["page"] == ["3"]
    assert query["attrFilter"] == ["emd_cd:=:11650108"]
    assert query["columns"] == ["emd_cd"]
    assert query["geometry"] == ["false"]
    assert query["domain"] == [""]


async def test_iter_data_feature_items_follows_pages_and_caps_items(client, http_mock):
    http_mock.add(
        "GET",
        BASE + "/req/data",
        json={
            "response": {
                "status": "OK",
                "record": {"total": "4", "current": "2"},
                "page": {"total": "2", "current": "1", "size": "2"},
                "result": {"items": [{"id": "1"}, {"id": "2"}]},
            }
        },
    )
    http_mock.add(
        "GET",
        BASE + "/req/data",
        json={
            "response": {
                "status": "OK",
                "record": {"total": "4", "current": "2"},
                "page": {"total": "2", "current": "2", "size": "2"},
                "result": {"items": [{"id": "3"}, {"id": "4"}]},
            }
        },
    )

    items = [
        item
        async for item in client.iter_data_feature_items("LT_C_ADEMD_INFO", size=2, max_items=3)
    ]

    assert [item["id"] for item in items] == ["1", "2", "3"]
    assert _query(http_mock.calls[0])["page"] == ["1"]
    assert _query(http_mock.calls[1])["page"] == ["2"]


async def test_client_close_and_context_manager(ok_payload, http_mock):
    http_mock.add("GET", BASE + "/req/search", json=ok_payload)

    async with VworldClient("test-key", retry_backoff=0) as c:
        (await c.search_place("판교"))

    # After exiting the context manager, the client should still be usable
    # for attribute access (close doesn't nullify the http object).
    assert c.api_key == "test-key"

    # Explicitly test close() on a standalone client
    standalone = VworldClient("test-key", retry_backoff=0)
    await standalone.aclose()
