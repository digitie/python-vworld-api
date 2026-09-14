"""공개 API 전체의 공통 과금과 디버그 동시성·수명 계약을 검증한다."""

import asyncio

import httpx
import pytest

from vworld import AsyncTokenBucket, VworldClient, debug_search
from vworld.exceptions import VworldAuthError


class CountingBucket(AsyncTokenBucket):
    def __init__(self):
        super().__init__(10000)
        self.calls = 0

    async def acquire(self):
        await super().acquire()
        self.calls += 1


def payload(page=1, query="query"):
    return {
        "response": {
            "status": "OK",
            "record": {"total": "2", "current": "1"},
            "page": {"total": "2", "current": str(page), "size": "1"},
            "result": {"items": [{"id": query}]},
        }
    }


async def test_shared_budget_covers_pages_debug_images_retries_and_redirects():
    bucket = CountingBucket()
    image_attempts = 0
    requests = []

    async def handler(request):
        nonlocal image_attempts
        requests.append(request)
        if request.url.path == "/req/search":
            return httpx.Response(200, json=payload(int(request.url.params["page"])))
        if request.url.path == "/req/image":
            image_attempts += 1
            if image_attempts == 1:
                return httpx.Response(503)
            return httpx.Response(302, headers={"location": "/final"})
        return httpx.Response(200, content=b"image", headers={"content-type": "image/png"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as session:
        async with (
            VworldClient("key", session=session, rate_limiter=bucket, retry_backoff=0) as first,
            VworldClient("key", session=session, rate_limiter=bucket, max_rps=-1) as second,
        ):
            pages = [page async for page in first.iter_search_pages("query", "place", size=1)]
            assert len(pages) == 2
            run = await debug_search(second, {"query": "query", "type": "place"})
            assert run.error is None
            assert run.response["status_code"] == 200
            image = await first.static_map(center=(127, 37), zoom=10, size=(128, 128))
            assert image.content == b"image"
            tile = await second.get_wmts_tile("Base", 11, 793, 1746)
            assert tile.content == b"image"
            assert "key" not in requests[-1].url.params
        assert not session.is_closed
    assert bucket.calls == len(requests) == 7


async def test_concurrent_debug_runs_keep_their_own_response_and_restore_context():
    entered = 0
    both_entered = asyncio.Event()

    async def handler(request):
        nonlocal entered
        entered += 1
        if entered == 2:
            both_entered.set()
        await both_entered.wait()
        return httpx.Response(200, json=payload(query=request.url.params["query"]))

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as session,
        VworldClient("key", session=session) as client,
    ):
        runs = await asyncio.gather(
            debug_search(client, {"query": "first"}),
            debug_search(client, {"query": "second"}),
        )
        for run, query in zip(runs, ["first", "second"], strict=True):
            assert run.request["query"]["query"] == query
            assert run.response["body"]["response"]["result"]["items"][0]["id"] == query
        assert client._require_http()._captures.get() is None
        assert client._require_http().session is session


async def test_owned_session_closes_after_cancel_and_closed_client_rejects_io(monkeypatch):
    entered = asyncio.Event()

    async def handler(request):
        entered.set()
        await asyncio.Event().wait()

    session = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("vworld._http._new_async_client", lambda: session)
    client = VworldClient("key")

    async def run():
        async with client:
            await debug_search(client, {"query": "query"})

    task = asyncio.create_task(run())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert session.is_closed
    assert client._require_http()._captures.get() is None
    with pytest.raises(RuntimeError, match="closed"):
        await client.search_place("query")


async def test_error_classification_precedes_key_redaction_and_debug_body_is_redacted():
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "response": {
                    "status": "ERROR",
                    "error": {"code": "INVALID_KEY", "text": "KEY rejected"},
                }
            },
        )

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as session,
        VworldClient("KEY", session=session) as client,
    ):
        with pytest.raises(VworldAuthError) as caught:
            await client.search_place("query")
        assert "KEY" not in str(caught.value)
        run = await debug_search(client, {"query": "query"})
        assert run.error["type"] == "VworldAuthError"
        assert "KEY" not in str(run.response)


def test_invalid_rate_and_sync_session_are_rejected_before_pool_creation(monkeypatch):
    def unexpected():
        raise AssertionError("HTTP pool must not be created")

    monkeypatch.setattr("vworld._http._new_async_client", unexpected)
    with pytest.raises(ValueError):
        VworldClient("key", max_rps=0)
    with httpx.Client() as session, pytest.raises(TypeError, match="asynchronous"):
            VworldClient("key", session=session)


async def test_debug_accepts_custom_session_response_without_bound_request():
    class Session:
        async def get(self, *args, **kwargs):
            return httpx.Response(200, json=payload())

    async with VworldClient("key", session=Session()) as client:
        run = await debug_search(client, {"query": "query"})
    assert run.error is None
    assert run.response["status_code"] == 200
    assert run.request["headers"] == {}


async def test_debug_parser_validation_error_redacts_key_from_message_and_traceback():
    key = "reviewer-fake-key"

    async def handler(request):
        return httpx.Response(200, json={"response": key})

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as session,
        VworldClient(key, session=session) as client,
    ):
        run = await debug_search(client, {"query": "query"})
    assert run.error is not None
    assert key not in str(run.error)
    assert key not in str(run.response)


async def test_debug_metadata_error_is_structured_and_does_not_replace_cancellation(monkeypatch):
    import vworld.debug as debug

    def broken_record(*args):
        raise ValueError("metadata failure")

    monkeypatch.setattr(debug, "_record_call", broken_record)

    async def handler(request):
        return httpx.Response(200, json=payload(query="key"))

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as session,
        VworldClient("key", session=session) as client,
    ):
        run = await debug_search(client, {"query": "query"})
        assert run.error["type"] == "ValueError"
        assert "key" not in str(run.response)

        async def cancelled_parser_call(client, params):
            await client.search_place("query")
            raise asyncio.CancelledError

        monkeypatch.setattr(debug, "_call_search", cancelled_parser_call)
        with client._require_http().capture_responses() as outer:
            with pytest.raises(asyncio.CancelledError):
                await debug_search(client, {"query": "query"})
            assert client._require_http()._captures.get() is outer
