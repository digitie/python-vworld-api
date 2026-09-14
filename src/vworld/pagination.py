"""VWorld 페이지네이션 JSON 응답을 다루는 헬퍼."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from .exceptions import VworldInvalidParameterError, VworldServerError

TPage = TypeVar("TPage", bound=Mapping[str, Any])


@dataclass(frozen=True, slots=True)
class VworldPageInfo:
    """``response.page``와 ``response.record``에서 읽은 페이지 메타데이터."""

    total: int
    current: int
    size: int
    record_total: int | None = None
    record_current: int | None = None


def response_root(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """VWorld 최상위 ``response`` 객체를 반환합니다."""

    root = payload.get("response")
    if not isinstance(root, Mapping):
        raise VworldServerError("response must be an object")
    return root


def response_status(payload: Mapping[str, Any]) -> str | None:
    """``response.status``가 있으면 문자열로 반환합니다."""

    status = response_root(payload).get("status")
    return str(status) if status is not None else None


def response_page_info(payload: Mapping[str, Any]) -> VworldPageInfo:
    """Search/Data API 응답의 페이지 메타데이터를 반환합니다."""

    root = response_root(payload)
    page = root.get("page")
    if not isinstance(page, Mapping):
        raise VworldServerError("response.page must be an object")

    record = root.get("record")
    record_total: int | None = None
    record_current: int | None = None
    if record is not None:
        if not isinstance(record, Mapping):
            raise VworldServerError("response.record must be an object")
        record_total = _int_from_mapping(record, "total", "response.record")
        record_current = _int_from_mapping(record, "current", "response.record")

    return VworldPageInfo(
        total=_int_from_mapping(page, "total", "response.page"),
        current=_int_from_mapping(page, "current", "response.page"),
        size=_int_from_mapping(page, "size", "response.page"),
        record_total=record_total,
        record_current=record_current,
    )


def has_next_page(payload: Mapping[str, Any]) -> bool:
    """VWorld 페이지 응답에 다음 페이지가 있는지 반환합니다."""

    page = response_page_info(payload)
    return page.current < page.total


def next_page_no(payload: Mapping[str, Any]) -> int | None:
    """다음 페이지 번호를 반환하고 마지막 페이지면 ``None``을 반환합니다."""

    if not has_next_page(payload):
        return None
    return response_page_info(payload).current + 1


def response_items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """``response.result.items``를 dict 목록으로 반환합니다.

    VWorld JSON은 보통 ``items``를 목록으로 반환하지만, XML 형태를 옮긴
    JSON에서는 ``items.item``으로 나타날 수 있습니다. 두 형태를 여기서
    같은 구조로 정규화합니다.
    """

    result = response_root(payload).get("result")
    if result is None:
        return []
    if not isinstance(result, Mapping):
        raise VworldServerError("response.result must be an object")
    return _normalize_items(result.get("items"), "response.result.items")


async def iter_pages(
    fetch_page: Callable[[int], Awaitable[TPage]],
    *,
    start_page: int = 1,
    max_pages: int = 100,
    max_items: int | None = None,
) -> AsyncIterator[TPage]:
    """``response.page`` 메타데이터를 따라 VWorld 페이지를 순회합니다.

    상위 API가 일관되지 않은 페이지 메타데이터를 반환할 때 무한 루프에
    빠지지 않도록 ``max_pages``와 ``max_items``를 명시적인 가드로 둡니다.
    """

    if start_page < 1:
        raise VworldInvalidParameterError("start_page must be at least 1")
    if max_pages < 1:
        raise VworldInvalidParameterError("max_pages must be at least 1")
    if max_items is not None and max_items < 1:
        raise VworldInvalidParameterError("max_items must be at least 1")

    page_no = start_page
    pages_seen = 0
    items_seen = 0
    while pages_seen < max_pages:
        payload = await fetch_page(page_no)
        yield payload

        pages_seen += 1
        items_seen += _item_count(payload)
        if max_items is not None and items_seen >= max_items:
            return

        next_page = next_page_no(payload)
        if next_page is None:
            return
        page_no = next_page


def _int_from_mapping(values: Mapping[str, Any], key: str, field: str) -> int:
    value = values.get(key)
    if value is None:
        raise VworldServerError(f"{field}.{key} is missing")
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise VworldServerError(f"{field}.{key} must be an integer") from exc


def _item_count(payload: Mapping[str, Any]) -> int:
    info = response_page_info(payload)
    if info.record_current is not None:
        return info.record_current
    return len(response_items(payload))


def _normalize_items(value: Any, field: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        if "item" in value:
            return _normalize_items(value["item"], f"{field}.item")
        return [_dict_from_mapping(value, field)]
    if isinstance(value, list | tuple):
        items: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                raise VworldServerError(f"{field}[{index}] must be an object")
            items.append(_dict_from_mapping(item, f"{field}[{index}]"))
        return items
    raise VworldServerError(f"{field} must be an object or list")


def _dict_from_mapping(value: Mapping[Any, Any], field: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise VworldServerError(f"{field} keys must be strings")
        result[key] = item
    return result
