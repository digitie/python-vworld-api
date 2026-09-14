from __future__ import annotations

import pytest

from vworld import VworldClient
from vworld.debug import (
    _bool_value,
    _required_text,
    debug_geocode,
    debug_reverse_geocode,
    debug_search,
    run_debug_function,
)

BASE = "https://api.vworld.kr"

_OK_RESPONSE = {
    "response": {
        "status": "OK",
        "result": {"items": [{"id": "1"}]},
        "record": {"total": "1", "current": "1"},
        "page": {"total": "1", "current": "1", "size": "10"},
    }
}


async def test_run_debug_function_unknown_raises_value_error(client):
    with pytest.raises(ValueError, match="Unknown debug function"):
        (await run_debug_function(client, "no_such_function", {}))


async def test_debug_search_with_valid_mock_data(http_mock):
    http_mock.add("GET", BASE + "/req/search", json=_OK_RESPONSE)

    client = VworldClient("test-key", retry_backoff=0)
    run = await debug_search(client, {"query": "판교", "type": "place"})

    assert run.function == "search"
    assert run.input["query"] == "판교"
    assert run.error is None
    assert run.processed is not None
    assert run.processed.items == [{"id": "1"}]
    assert len(run.trace) >= 2


async def test_debug_geocode_with_valid_mock_data(http_mock):
    http_mock.add("GET", BASE + "/req/address", json=_OK_RESPONSE)

    client = VworldClient("test-key", retry_backoff=0)
    run = await debug_geocode(client, {"address": "판교로 242"})

    assert run.function == "geocode"
    assert run.error is None
    assert run.parsed is not None
    assert run.processed is not None


async def test_debug_reverse_geocode_with_valid_mock_data(http_mock):
    http_mock.add("GET", BASE + "/req/address", json=_OK_RESPONSE)

    client = VworldClient("test-key", retry_backoff=0)
    run = await debug_reverse_geocode(client, {"point": "127.101313354,37.402352535"})

    assert run.function == "reverse_geocode"
    assert run.error is None
    assert run.parsed is not None
    assert run.processed is not None


def test_required_text_returns_empty_string_when_key_missing():
    result = _required_text({}, "missing_key")
    assert result == ""


def test_bool_value_handles_various_input_types():
    assert _bool_value(None, True) is True
    assert _bool_value(None, False) is False
    assert _bool_value("", True) is True
    assert _bool_value(True, False) is True
    assert _bool_value(False, True) is False
    assert _bool_value(1, False) is True
    assert _bool_value(0, True) is False
    assert _bool_value("true", False) is True
    assert _bool_value("false", True) is False
    assert _bool_value("yes", False) is True
    assert _bool_value("no", True) is False
    assert _bool_value("on", False) is True
    assert _bool_value("off", True) is False
    assert _bool_value("1", False) is True
    assert _bool_value("0", True) is False
    assert _bool_value("maybe", True) is True
    assert _bool_value("maybe", False) is False
