from __future__ import annotations

import pytest

from vworld.exceptions import VworldInvalidParameterError, VworldServerError
from vworld.pagination import (
    has_next_page,
    iter_pages,
    next_page_no,
    response_items,
    response_page_info,
    response_status,
)


def _payload(
    *,
    page: int = 1,
    total_pages: int = 2,
    size: int = 2,
    record_current: int = 2,
    items: object | None = None,
) -> dict[str, object]:
    return {
        "response": {
            "status": "OK",
            "record": {"total": "4", "current": str(record_current)},
            "page": {"total": str(total_pages), "current": str(page), "size": str(size)},
            "result": {"items": items if items is not None else [{"id": "a"}, {"id": "b"}]},
        }
    }


def test_response_page_info_and_next_page_helpers() -> None:
    payload = _payload(page=1, total_pages=3)

    info = response_page_info(payload)

    assert info.total == 3
    assert info.current == 1
    assert info.size == 2
    assert info.record_total == 4
    assert response_status(payload) == "OK"
    assert has_next_page(payload) is True
    assert next_page_no(payload) == 2
    assert next_page_no(_payload(page=3, total_pages=3)) is None


def test_response_items_accepts_json_list_and_xml_shaped_item_root() -> None:
    assert response_items(_payload(items=[{"id": "a"}, {"id": "b"}])) == [
        {"id": "a"},
        {"id": "b"},
    ]
    assert response_items(_payload(items={"item": {"id": "single"}})) == [{"id": "single"}]
    assert response_items(_payload(items={"item": [{"id": "nested"}]})) == [{"id": "nested"}]


async def test_iter_pages_follows_response_page_with_item_guard() -> None:
    calls: list[int] = []

    async def fetch(page_no: int) -> dict[str, object]:
        calls.append(page_no)
        return _payload(page=page_no, total_pages=3, record_current=2)

    pages = [item async for item in iter_pages(fetch, max_items=3)]

    assert calls == [1, 2]
    assert len(pages) == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start_page": 0},
        {"max_pages": 0},
        {"max_items": 0},
    ],
)
async def test_iter_pages_rejects_bad_guards(kwargs: dict[str, int]) -> None:
    with pytest.raises(VworldInvalidParameterError):
        [item async for item in iter_pages(lambda page: _payload(page=page), **kwargs)]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"response": {"page": "bad"}},
        {"response": {"page": {"total": "bad", "current": "1", "size": "10"}}},
    ],
)
def test_page_info_rejects_bad_response_shapes(payload: dict[str, object]) -> None:
    with pytest.raises(VworldServerError):
        response_page_info(payload)


def test_response_items_rejects_non_object_items() -> None:
    with pytest.raises(VworldServerError):
        response_items({"response": {"result": {"items": ["not-an-object"]}}})
