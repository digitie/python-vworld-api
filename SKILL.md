---
name: vworld-builder
description: VWorld REST, OGC, image, WMTS, TMS API용 `vworld` Python client를 구현, 확장, test, 문서화할 때 사용한다.
---

# vworld Builder — 에이전트 매뉴얼

> 이 파일은 당신(AI 에이전트)이 작업을 시작하기 전 반드시 읽어야 한다.

## 1. 정체성

이 저장소(GitHub 이름 `python-vworld-api`, Python 패키지 `vworld`)는 VWorld REST, OGC, 정적 이미지, WMTS/TMS API를 래핑하는 비공식 Python 클라이언트다. `VworldClient` 하나로 native async 호출을 제공한다.

## 2. 먼저 읽을 것

1. `README.md` — 프로젝트 개요와 빠른 시작
2. `vworld-api.md` — VWorld API 공식 참조 정리
3. `docs/resume.md` — 현재 진척도와 "다음 한 작업"
4. `docs/api-coverage.md` — 구현 범위
5. `docs/repeated-mistakes.md` — 반복 실수

## 3. 디렉토리 지도

```
src/vworld/
  client.py      # VworldClient native async 진입점
  _http.py       # HTTP helper, 오류-예외 매핑
  _params.py     # 파라미터 정규화, 검증
  models.py      # 공개 Pydantic v2 모델, enum
  catalog.py     # 공식 158-entry API 카탈로그
  parser.py      # VWorld JSON → Pydantic 파싱
  processor.py   # 파싱 결과 → 공통 비교 형태 정규화
  debug.py       # fixture 생성용 디버그 실행기
  metadata.py    # 응답 메타데이터, 민감정보 제거
  pagination.py  # 페이지네이션 헬퍼
  exceptions.py  # 예외 계층

debug-ui/          # Streamlit 디버그 UI (별도 패키지)
tests/             # offline 테스트 + live smoke 테스트
docs/              # 프로젝트 문서
```

## 4. 불변 조건

- Search, Geocoder, 2D Data, Legend, StaticMap은 VWorld API 2.0만 사용한다.
- WMS/WFS OGC protocol version은 VWorld API 1.0이 아니다.
- WMTS/TMS는 query parameter가 아니라 path에 key를 둔다.
- 기본 test는 offline이어야 한다.
- Error mapping은 `src/vworld/_http.py`가 소유한다.
- Sync/Async validation·param 로직은 `_make_*_params()` 공유 함수를 사용한다.
- fixture/history 저장 전 `redact_sensitive()`로 모든 필드를 마스킹한다.

## 5. 절대 하지 말 것 (DO NOT)

`AGENTS.md` §절대 하지 말 것과 동일하지만 핵심만 다시 적는다:

1. API key 평문 커밋 금지.
2. Sync/Async 로직 분기 금지 — `_make_*_params()` 공유 함수 사용.
3. 단순 전달용 wrapper 금지.
4. HTTP 오류 매핑 분산 금지 — `_http.py`에만 둔다.
5. 1.0 API 구현 금지.
6. 기본 테스트에서 라이브 네트워크 호출 금지.
7. 문서에 절대 경로 금지.

## 6. 자주 묻는 작업

| 작업 | 시작 파일 |
|------|-----------|
| 새 엔드포인트 추가 | `src/vworld/client.py` → `tests/test_client_rest.py` |
| 새 데이터 서비스 추가 | `src/vworld/catalog.py` → `tests/test_catalog.py` |
| 에러 매핑 추가 | `src/vworld/_http.py` → `tests/test_http.py` |
| 디버그 함수 추가 | `src/vworld/debug.py` → `tests/test_debug.py` |
| fixture 포맷 변경 | `debug-ui/vworld_debug_ui/fixture_writer.py` |

## 7. 도메인 어휘

| 용어 | 의미 |
|------|------|
| Search API | 장소/주소/행정동/도로명 검색 (REST 2.0) |
| Geocoder | 주소→좌표(getcoord), 좌표→주소(getaddress) |
| 2D Data | GetFeature, GetFeatureType (공간 데이터 조회) |
| StaticMap | 정적 지도 이미지 생성 |
| WMTS/TMS | 타일 맵 서비스 (path에 key 포함) |
| WMS/WFS | OGC 표준 맵/피처 서비스 |

## 8. 필수 확인

```bash
python -m compileall src/vworld tests
python -m pytest
python -m ruff check .
python -m mypy src/vworld
```

## 9. Endpoint 추가 절차

1. 공식 VWorld page와 version을 확인한다.
2. `_make_*_params()` 공유 함수를 추가한다.
3. `VworldClient`에 async 메서드를 추가한다. 요청 파라미터는 공유 `_make_*_params` 함수에서 조립한다.
4. 정확한 path/query shape를 assert하는 test를 추가한다.
5. 사용자-facing 변경이면 `docs/api-coverage.md`와 README를 갱신한다.
6. 새 gotcha는 `docs/repeated-mistakes.md`에 추가한다.

## 10. 작업 후 체크리스트

- [ ] `python -m pytest` 통과
- [ ] `python -m ruff check .` / `python -m mypy src/vworld` 통과
- [ ] `docs/journal.md`에 작업 항목 추가 (역시간순)
- [ ] `docs/resume.md`의 진척도 갱신
- [ ] 의사결정이 있었다면 `docs/decisions.md`에 ADR 추가
- [ ] 사용자 가시 변경이면 `CHANGELOG.md` 갱신


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


상세 예제: [docs/async-tps.md](docs/async-tps.md).
