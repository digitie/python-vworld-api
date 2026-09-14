# 비동기 호출과 요청 속도 제어

## async-only와 TPS 계약

`VworldClient`의 네트워크 메서드는 `await`, 페이지/항목 반복은 `async for`,
종료는 `async with` 또는 `await client.aclose()`를 사용한다. Async 접두사
클라이언트·aio 팩터리·동기 HTTP 진입점은 제거했다. URL 빌더와 순수 메타데이터·
좌표·파싱 함수는 일반 함수로 유지한다.

기본 `max_rps=5.0`이며 `AsyncTokenBucket(max_rps, capacity=...)`를
`rate_limiter=`에 주입하면 여러 클라이언트가 같은 예산을 쓴다. 주입한 버킷이
max_rps보다 우선한다. REST·OGC·이미지·타일·debug·페이지의 실제 요청과
각 재시도·리다이렉트마다 토큰을 얻는다. 검증 실패와 URL 생성은 과금하지 않는다.

버킷은 초기 용량만큼 가득 차 시작한다. 기본 capacity는 max(1, max_rps)여서
초기 burst가 가능하며 엄격한 간격이 필요하면 capacity=1을 지정한다. 대기 취소는
토큰을 소비하지 않고 다음 대기자를 진행시킨다. 한 버킷은 한 이벤트 루프에서 사용한다.
HTTPX의 기본 리다이렉트는 각 송신을 계측하지만 사용자 정의 인증 흐름이나 transport
내부 재시도는 라이브러리 바깥의 동작이다.

내부 HTTP 세션은 첫 요청에서 생성하고 문맥 종료 시 닫는다. 주입하는 세션은
비동기 get을 제공해야 하며 수명은 호출자가 관리한다. 디버그는 ContextVar로
현재 호출의 응답만 수집하고 종료·취소 시 복원한다.

```python
import asyncio
from vworld import AsyncTokenBucket, VworldClient


async def main() -> None:
    bucket = AsyncTokenBucket(2, capacity=1)
    async with VworldClient.from_env(rate_limiter=bucket) as client:
        async for item in client.iter_search_items("판교", "place", max_pages=2):
            print(item)


asyncio.run(main())
```
