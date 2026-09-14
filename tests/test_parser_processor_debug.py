from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from vworld import VworldClient
from vworld.debug import debug_get_data_feature, debug_search
from vworld.parser import parse_search_response
from vworld.processor import process_search_response

BASE = "https://api.vworld.kr"


def test_parser_and_processor_normalize_items() -> None:
    raw = {
        "response": {
            "status": "OK",
            "record": {"total": "1", "current": "1"},
            "page": {"total": "1", "current": "1", "size": "10"},
            "result": {"items": {"id": "one"}},
        }
    }

    parsed = parse_search_response(raw)
    processed = process_search_response(parsed)

    assert parsed.response["status"] == "OK"
    assert processed.items == [{"id": "one"}]
    assert processed.status == "OK"


async def test_debug_search_captures_request_response_and_processed_result(http_mock) -> None:
    http_mock.add(
        "GET",
        BASE + "/req/search",
        json={
            "response": {
                "status": "OK",
                "record": {"total": "1", "current": "1"},
                "page": {"total": "1", "current": "1", "size": "10"},
                "result": {"items": [{"id": "one"}]},
            }
        },
    )

    run = await debug_search(
        VworldClient("secret-key", retry_backoff=0),
        {"query": "판교", "type": "place", "size": 10, "page": 1},
    )

    query = parse_qs(urlparse(str(http_mock.calls[0].request.url)).query)
    assert query["key"] == ["secret-key"]
    assert "secret-key" not in run.request["url"]
    assert "key" not in run.request["query"]
    assert run.response["status_code"] == 200
    assert run.processed is not None
    assert run.processed.items == [{"id": "one"}]
    assert run.catalog is not None
    assert run.catalog.function == "search"
    assert run.error is None


async def test_debug_data_feature_includes_dataset_catalog_item(http_mock) -> None:
    http_mock.add(
        "GET",
        BASE + "/req/data",
        json={
            "response": {
                "status": "OK",
                "record": {"total": "0", "current": "0"},
                "page": {"total": "1", "current": "1", "size": "10"},
                "result": {"items": []},
            }
        },
    )

    client = VworldClient("secret-key", retry_backoff=0)
    debug_run = await debug_get_data_feature(client, {"data": "LT_C_ADEMD_INFO"})

    assert debug_run.catalog is not None
    assert debug_run.catalog.function == "get_data_feature"
    assert debug_run.data_service is not None
    assert debug_run.data_service.name == "읍면동"


async def test_debug_search_returns_error_when_auth_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("VWORLD_API_KEY", raising=False)
    monkeypatch.delenv("VWORLD_KEY", raising=False)

    run = await debug_search(VworldClient(api_key=None), {"query": "판교", "type": "place"})

    assert run.error is not None
    assert run.error["type"] == "VworldAuthError"
    assert run.request == {}
    assert run.response == {}


async def test_debug_search_keeps_vworld_error_body_for_fixture_review(http_mock) -> None:
    http_mock.add(
        "GET",
        BASE + "/req/search",
        json={
            "response": {
                "status": "ERROR",
                "error": {"code": "INVALID_PARAMETER", "text": "bad query"},
            }
        },
    )

    run = await debug_search(
        VworldClient("secret-key", retry_backoff=0),
        {"query": "판교", "type": "place"},
    )

    assert run.error is not None
    assert run.response["body"]["response"]["status"] == "ERROR"
    assert run.processed is not None
    assert run.processed.error == {"code": "INVALID_PARAMETER", "text": "bad query"}
