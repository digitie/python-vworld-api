"""비동기 HTTP 요청, 요청별 TPS 제어와 오류 매핑."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from urllib.parse import quote, urlencode, urljoin

import httpx

from ._httpx import send_after_token
from ._params import Params, clean_params
from ._ratelimit import AsyncTokenBucket
from .exceptions import (
    VworldAuthError,
    VworldError,
    VworldNetworkError,
    VworldNoDataError,
    VworldRateLimitError,
    VworldServerError,
)


def _new_async_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=True)


def _redact_text(text: str, api_key: str) -> str:
    if not api_key:
        return text
    return text.replace(api_key, "***").replace(quote(api_key, safe=""), "***")


@dataclass(slots=True)
class _VworldHttp:
    api_key: str = field(repr=False)
    timeout: float = 10.0
    max_retries: int = 2
    retry_backoff: float = 0.5
    session: Any = None
    max_rps: float = 5.0
    rate_limiter: AsyncTokenBucket | None = None
    _owns_session: bool = field(init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _captures: ContextVar[list[tuple[Any, float]] | None] = field(
        default_factory=lambda: ContextVar("vworld_responses", default=None), init=False, repr=False
    )

    BASE_URL = "https://api.vworld.kr"

    def __post_init__(self) -> None:
        if self.rate_limiter is None:
            self.rate_limiter = AsyncTokenBucket(self.max_rps)
        self._owns_session = self.session is None
        if self.session is not None and not inspect.iscoroutinefunction(self.session.get):
            raise TypeError("session.get must be asynchronous")

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_session and self.session is not None:
            await self.session.aclose()

    @contextmanager
    def capture_responses(self) -> Iterator[list[tuple[Any, float]]]:
        """현재 호출 문맥의 응답만 수집하고 종료·취소 시 이전 문맥을 복원한다."""
        records: list[tuple[Any, float]] = []
        token = self._captures.set(records)
        try:
            yield records
        finally:
            self._captures.reset(token)

    @contextmanager
    def _redact_errors(self) -> Iterator[None]:
        try:
            yield
        except VworldError as exc:
            exc.args = (_redact_text(str(exc), self.api_key),)
            raise exc from None

    def build_url(
        self,
        path: str,
        params: Params | None = None,
        *,
        include_key: bool = True,
    ) -> str:
        return _build_url(self.api_key, self.BASE_URL, path, params, include_key=include_key)

    async def get_json(self, path: str, params: Params | None = None) -> dict[str, Any]:
        with self._redact_errors():
            response = await self._get(path, params)
            _raise_for_http_status(response)
            data = _json_object(response)
            _raise_for_vworld_status(data)
            return data

    async def get_bytes(
        self,
        path: str,
        params: Params | None = None,
        *,
        include_key: bool = True,
    ) -> tuple[bytes, str | None]:
        with self._redact_errors():
            response = await self._get(path, params, include_key=include_key)
            _raise_for_http_status(response)
            _raise_if_error_payload(response)
            return bytes(response.content), _content_type(response)

    async def get_text(
        self,
        path: str,
        params: Params | None = None,
        *,
        include_key: bool = True,
    ) -> tuple[str, str | None]:
        with self._redact_errors():
            response = await self._get(path, params, include_key=include_key)
            _raise_for_http_status(response)
            _raise_if_error_payload(response)
            return str(response.text), _content_type(response)

    async def _get(self, path: str, params: Params | None, *, include_key: bool = True) -> Any:
        if self._closed:
            raise RuntimeError("VworldClient is closed")
        query = _query_params(self.api_key, params, include_key=include_key)
        attempts = max(0, self.max_retries) + 1
        if self.session is None:
            self.session = _new_async_client()
        assert self.rate_limiter is not None
        for attempt in range(attempts):
            await self.rate_limiter.acquire()
            started = perf_counter()
            try:
                if isinstance(self.session, httpx.AsyncClient):
                    request = self.session.build_request(
                        "GET", urljoin(self.BASE_URL, path), params=query, timeout=self.timeout
                    )
                    response = await send_after_token(self.session, request, self.rate_limiter)
                else:
                    response = await self.session.get(
                        urljoin(self.BASE_URL, path),
                        params=query,
                        timeout=self.timeout,
                    )
            except httpx.HTTPError as exc:
                if attempt < attempts - 1:
                    await self._sleep_before_retry(attempt)
                    continue
                raise VworldNetworkError(_redact_text(str(exc), self.api_key)) from None
            records = self._captures.get()
            if records is not None:
                records.append((response, round((perf_counter() - started) * 1000, 3)))
            if 500 <= response.status_code < 600 and attempt < attempts - 1:
                await self._sleep_before_retry(attempt)
                continue
            return response
        raise VworldServerError("request failed after retries")

    async def _sleep_before_retry(self, attempt: int) -> None:
        if self.retry_backoff > 0:
            await asyncio.sleep(self.retry_backoff * (2**attempt))


def _query_params(
    api_key: str,
    params: Params | None,
    *,
    include_key: bool,
) -> dict[str, Any]:
    query = clean_params(params or {})
    if include_key:
        query.setdefault("key", api_key)
    return query


def _build_url(
    api_key: str,
    base_url: str,
    path: str,
    params: Params | None,
    *,
    include_key: bool,
) -> str:
    query = _query_params(api_key, params, include_key=include_key)
    url = urljoin(base_url, path)
    if not query:
        return url
    return f"{url}?{urlencode(query, doseq=True)}"


def _json_object(response: Any) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise VworldServerError(f"JSON parse failure: {exc}") from exc
    if not isinstance(data, dict):
        raise VworldServerError("JSON response must be an object")
    return data


def _raise_for_http_status(response: Any) -> None:
    if response.status_code in (401, 403):
        raise VworldAuthError(f"HTTP {response.status_code}: {response.text[:200]}")
    if response.status_code == 429:
        raise VworldRateLimitError(response.text[:200])
    if 500 <= response.status_code < 600:
        raise VworldServerError(f"HTTP {response.status_code}: {response.text[:200]}")
    if response.status_code >= 400:
        raise VworldServerError(f"HTTP {response.status_code}: {response.text[:200]}")


def _raise_if_error_payload(response: Any) -> None:
    content_type = (_content_type(response) or "").lower()
    text = str(response.text[:1000]).lstrip()
    if "json" in content_type or text.startswith("{"):
        try:
            data = response.json()
        except ValueError:
            return
        if isinstance(data, dict):
            _raise_for_vworld_status(data)
    elif "ExceptionReport" in text or "TileMapServerError" in text:
        raise VworldServerError(text[:300])


def _raise_for_vworld_status(data: dict[str, Any]) -> None:
    root = data.get("response")
    if not isinstance(root, dict):
        return
    status = str(root.get("status", "")).upper()
    if status == "OK":
        return
    if status == "NOT_FOUND":
        raise VworldNoDataError("VWorld returned NOT_FOUND")
    if status != "ERROR":
        return

    error = root.get("error")
    if isinstance(error, dict):
        code = str(error.get("code", "UNKNOWN_ERROR"))
        text = str(error.get("text", ""))
    else:
        code = "UNKNOWN_ERROR"
        text = str(error or "")
    message = f"{code}: {text}".strip()
    if code in {"INVALID_KEY", "INCORRECT_KEY", "UNAVAILABLE_KEY"}:
        raise VworldAuthError(message)
    if code == "OVER_REQUEST_LIMIT":
        raise VworldRateLimitError(message)
    if code in {"SYSTEM_ERROR", "UNKNOWN_ERROR"}:
        raise VworldServerError(message)
    raise VworldServerError(message)


def _content_type(response: Any) -> str | None:
    value = response.headers.get("Content-Type")
    return str(value) if value is not None else None
