from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import pytest

from vworld import VworldClient
from vworld.exceptions import VworldAuthError, VworldNetworkError, VworldServerError

pytestmark = pytest.mark.live
T = TypeVar("T")


def _local_env() -> dict[str, str]:
    path = Path(".env")
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@pytest.fixture
async def live_client() -> VworldClient:
    local = _local_env()
    api_key = os.getenv("VWORLD_API_KEY") or os.getenv("VWORLD_KEY") or local.get("VWORLD_API_KEY")
    if not api_key:
        pytest.skip("VWORLD_API_KEY is required for live tests")
    domain = os.getenv("VWORLD_DOMAIN") or local.get("VWORLD_DOMAIN")
    async with VworldClient(
        api_key, domain=domain, timeout=20, max_retries=1, retry_backoff=0
    ) as client:
        yield client


def _status(payload: dict[str, Any]) -> str:
    response = payload.get("response")
    assert isinstance(response, dict)
    status = response.get("status")
    assert isinstance(status, str)
    return status


async def _live_call(
    call: Callable[[], Awaitable[T]],
    *,
    skip_auth_error: bool = False,
    skip_server_error: bool = False,
) -> T:
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            return await call()
        except (VworldAuthError, VworldNetworkError, VworldServerError) as exc:
            last_error = exc
            if attempt < 4:
                await asyncio.sleep(0.5)
    assert last_error is not None
    if skip_auth_error and isinstance(last_error, VworldAuthError):
        pytest.skip(f"live endpoint rejected the configured key: {last_error}")
    if skip_server_error and isinstance(last_error, VworldServerError):
        pytest.skip(f"live endpoint returned an OGC/server error: {last_error}")
    raise last_error


async def test_live_search_geocoder_and_data(live_client: VworldClient):
    search = await _live_call(
        lambda: live_client.search_address("성남시 분당구 판교로 242", size=1)
    )
    assert _status(search) == "OK"

    geocoded = await _live_call(lambda: live_client.geocode("판교로 242", type="road"))
    assert _status(geocoded) == "OK"
    point = geocoded["response"]["result"]["point"]
    x, y = float(point["x"]), float(point["y"])

    reverse = await _live_call(lambda: live_client.reverse_geocode((x, y), type="both"))
    assert _status(reverse) == "OK"

    async with VworldClient(
        live_client.api_key,
        domain="",
        timeout=20,
        max_retries=1,
        retry_backoff=0,
    ) as data_client:
        feature = await _live_call(
            lambda: data_client.get_data_feature(
                "LT_C_ADEMD_INFO",
                attr_filter="emd_cd:=:11650108",
                geometry=False,
                size=1,
            ),
            skip_auth_error=True,
        )
        assert _status(feature) == "OK"


async def test_live_ogc_capabilities(live_client: VworldClient):
    wms = await _live_call(
        lambda: live_client.wms_get_capabilities(domain=""),
        skip_auth_error=True,
        skip_server_error=True,
    )
    assert "WMS_Capabilities" in wms.text

    wfs = await _live_call(
        lambda: live_client.wfs_get_capabilities(domain=""),
        skip_auth_error=True,
        skip_server_error=True,
    )
    assert "WFS_Capabilities" in wfs.text


async def test_live_async_search(live_client: VworldClient):
    async def run() -> dict[str, Any]:
        async with VworldClient(
            live_client.api_key,
            domain=live_client.domain,
            timeout=20,
            max_retries=1,
            retry_backoff=0,
        ) as client:
            return await client.search_address("성남시 분당구 판교로 242", size=1)

    search = await _live_call(run)
    assert _status(search) == "OK"


async def test_live_images_and_tiles(live_client: VworldClient):
    legend = await _live_call(
        lambda: live_client.get_legend_graphic("lt_c_uq111", style="lt_c_uq111")
    )
    assert legend.content_type is not None
    assert "image" in legend.content_type.lower()
    assert len(legend.content) > 100

    static = await _live_call(
        lambda: live_client.static_map(center=(126.978271, 37.566643), zoom=16, size=(128, 128))
    )
    assert static.content_type is not None
    assert "image" in static.content_type.lower()
    assert len(static.content) > 100

    wmts_capabilities = await _live_call(lambda: live_client.get_wmts_capabilities())
    assert "Capabilities" in wmts_capabilities.text

    tile = await _live_call(lambda: live_client.get_wmts_tile("Base", 11, 793, 1746))
    assert tile.content_type is not None
    assert "image" in tile.content_type.lower()
    assert len(tile.content) > 100

    tms_resource = await _live_call(lambda: live_client.get_tms_resource())
    assert "TileMapService" in tms_resource.text
