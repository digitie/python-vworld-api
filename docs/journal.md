# 작업 기록

## 2026-09-14 — async-only와 공통 TPS

native async 클라이언트 통합, 페이지·디버그·UI 전환, 공통 버킷과 리다이렉트 과금, 취소·소유권·디버그 동시성 검증을 추가했다. 독립 리뷰와 live 결과는 별도 검증 문서에 기록한다.

역시간순으로 작업 내용을 기록한다.

## 2026-05-28

- `python-kraddr-base`를 런타임 의존성이나 소스 수준 DTO 계약으로 쓰지 않도록 `tests/test_dependency_boundaries.py`를 추가했다.
- `reverse_geocode_latlon`, `static_map_latlon`, `static_map_latlon_url`의 동기/비동기 구현이 `LatLon` 값 객체를 중간에 만들지 않고 `(lon, lat)` 기본 튜플로 요청 파라미터를 조립하게 정리했다.
- README, `docs/api-coverage.md`, `docs/repeated-mistakes.md`에 `PlaceCoordinate`/`Address` 같은 외부 DTO를 공개 입력으로 받지 않는 경계를 명시했다.

## 2025-05-23

- 코드 리뷰 보고서 작성 (Critical 2, Major 10, Minor 27, Suggestion 17)
- fixture_writer `parsed`/`processed` 필드에 `redact_sensitive()` 적용 (C-1)
- history_store에 `redact_sensitive()` 적용 + 동일 초 파일 덮어쓰기 방지 (M-5)
- HttpxMock teardown 시 미소비 라우트 검증 추가 (C-2)
- VworldClient/AsyncVworldClient validation·param 로직을 모듈 레벨 `_make_*_params()` 함수로 추출 (M-2)
- AsyncVworldClient 테스트 8건 추가 (search_address, search_district, search_road, reverse_geocode, reverse_geocode_latlon, get_data_feature_type, wms_get_capabilities, wfs_get_feature)
- iter_data_feature_items 테스트 추가 (M-3)
- debug 모듈 테스트 6건 추가 (M-8)
- close/context manager, metadata 변환, HTTP close 테스트 추가
- test_pagination 조건부 assertion을 개별 테스트로 분리
- docs/debug-ui.md, docs/testing.md 마스킹 범위 설명 정정 (M-4)
- pyproject.toml: project.urls 추가, 작성자 email 추가, Python 3.14 classifier 제거
- WSL 문서 절대 경로를 플레이스홀더로 교체
- app.py: 미사용 Environment 셀렉트박스 제거, 탭 간 에러 전파 처리
- fixture_writer URL redaction 패턴에 access_token/refresh_token 추가
- python-kraddr-geo 개발 방식 도입: AGENTS.md 강화, SKILL.md 에이전트 매뉴얼화, resume.md·journal.md·tasks.md·decisions.md 추가, ruff 규칙 확대
