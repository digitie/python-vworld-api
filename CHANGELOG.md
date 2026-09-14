# 변경 기록

## 미출시 — 호환성 변경

동기 VworldClient와 Async 접두사 클라이언트를 native async VworldClient 하나로 통합했다. 호출은 await, 페이지는 async for, 종료는 async with/aclose를 사용한다. max_rps/rate_limiter와 공통 AsyncTokenBucket을 공개한다. debug/UI·예제를 전환하고 동시 응답 수집과 주입 세션 수명을 보장한다.

## 0.1.0

- 초기 `python-vworld-api` package 추가.
- VWorld Search, Geocoder, 2D Data, WMS/WFS, Legend, StaticMap, WMTS, TMS wrapper 추가.
- 공식 2D Data API 2.0 catalog 158개 service ID 추가.
- Parameter normalization, HTTP error mapping, endpoint query construction, image/tile URL generation, catalog integrity를 확인하는 offline test 추가.
- 실제 VWorld server 검증을 위한 opt-in live smoke test 추가.
- `VworldClient.from_env_file()`을 통한 local `.env` loading 추가.
- 공개 enum, typed coordinate model, 공식 StaticMap/Image enum value, typed external usage를 위한 explicit domain override handling 추가.
- 공개 value/response model을 frozen Pydantic v2 model로 전환하고 기존 constructor와 validation exception을 보존.
- 내부 HTTP helper repr에서 API key를 숨김.
- 이후 유지보수를 위한 README와 implementation note 추가.
- `python-kraddr-base`를 런타임 의존성이나 공개 입력 계약으로 사용하지 않도록 경계 테스트와 문서를 추가하고, 위경도 편의 함수는 값 객체를 만들지 않고 기본 좌표로 요청을 조립하도록 정리.
