from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from vworld import VworldClient


@dataclass(slots=True)
class RecordedCall:
    request: httpx.Request


@dataclass(slots=True)
class _Route:
    method: str
    url: str
    status: int = 200
    body: bytes | str | None = None
    json: Any = None
    content_type: str | None = None


@dataclass(slots=True)
class HttpxMock:
    routes: list[_Route] = field(default_factory=list)
    calls: list[RecordedCall] = field(default_factory=list)

    def add(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        body: bytes | str | None = None,
        status: int = 200,
        content_type: str | None = None,
    ) -> None:
        self.routes.append(
            _Route(
                method=method.upper(),
                url=url,
                status=status,
                body=body,
                json=json,
                content_type=content_type,
            )
        )

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self._handle), follow_redirects=True)

    def async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(self._handle),
            follow_redirects=True,
        )

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(RecordedCall(request=request))
        request_url = str(request.url).split("?", 1)[0]
        for index, route in enumerate(self.routes):
            if route.method == request.method and route.url == request_url:
                matched = self.routes.pop(index)
                return self._response(matched, request)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    def _response(self, route: _Route, request: httpx.Request) -> httpx.Response:
        headers = {}
        if route.content_type is not None:
            headers["Content-Type"] = route.content_type
        if route.json is not None:
            return httpx.Response(
                route.status,
                json=route.json,
                headers=headers,
                request=request,
            )
        body = b"" if route.body is None else route.body
        content = body if isinstance(body, bytes) else body.encode()
        return httpx.Response(route.status, content=content, headers=headers, request=request)


@pytest.fixture
def http_mock() -> HttpxMock:
    mock = HttpxMock()
    yield mock
    unconsumed = [f"{r.method} {r.url}" for r in mock.routes]
    assert not unconsumed, f"unconsumed HttpxMock routes: {unconsumed}"


@pytest.fixture(autouse=True)
def _patch_default_httpx_clients(
    request: pytest.FixtureRequest,
    http_mock: HttpxMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if request.node.get_closest_marker("live") is not None:
        return

    import vworld._http as http_module

    monkeypatch.setattr(http_module, "_new_async_client", http_mock.async_client)


@pytest.fixture
async def client(http_mock: HttpxMock):
    async with VworldClient("test-key", retry_backoff=0, max_rps=10000) as instance:
        yield instance


@pytest.fixture
def ok_payload() -> dict[str, Any]:
    return {"response": {"status": "OK", "result": {"items": []}}}


BASE_URL = "https://api.vworld.kr"


def query_params(call: RecordedCall) -> dict[str, list[str]]:
    from urllib.parse import parse_qs, urlparse

    return parse_qs(urlparse(str(call.request.url)).query, keep_blank_values=True)
