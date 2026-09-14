# 현재 진척도

## 2026-09-14 현재 작업

async-only·공통 TPS 구현 및 오프라인 검증 완료. 독립 리뷰 2인, live E2E와 PR 머지 결과는 docs/verification-async-tps.md에서 이어 기록한다.

> 에이전트가 작업을 시작할 때 이 문서를 먼저 읽어 현재 상태를 파악한다.

## 마지막 갱신

2026-05-28

## 완료된 항목

- [x] VWorld REST API 2.0 클라이언트 (Search, Geocoder, 2D Data)
- [x] OGC API 래퍼 (WMS GetCapabilities/GetMap/GetFeatureInfo, WFS GetCapabilities/DescribeFeatureType/GetFeature)
- [x] Legend, StaticMap Image API 2.0
- [x] WMTS/TMS 타일 엔드포인트
- [x] VworldClient 하나로 통합한 native async HTTP 및 공통 TPS
- [x] 공식 2D Data 카탈로그 158개 service ID
- [x] Pydantic v2 공개 모델
- [x] 페이지네이션 헬퍼 (iter_pages, iter_items)
- [x] Streamlit 디버그 UI + fixture writer
- [x] fixture replay 테스트 프레임워크
- [x] Sync/Async validation·param 로직 공유 함수 추출 (DRY)
- [x] fixture/history 민감정보 마스킹 전면 적용
- [x] HttpxMock 미소비 라우트 검증 추가
- [x] `python-kraddr-base` 비의존 경계 테스트와 외부 DTO 배제 문서화

## 진행 중

(없음)

## 다음 한 작업

- 추가 fixture 데이터 확보: `geocode`, `reverse_geocode`, `get_data_feature`에 대한 fixture를 추가하여 replay 테스트 프레임워크를 실제로 활용한다.

## 알려진 주의사항

- VWorld는 같은 key와 request shape에도 간헐적으로 `INCORRECT_KEY`를 반환할 수 있다.
- WMS/WFS capabilities는 명시적 blank `domain=` query가 가장 안정적이다.
- 2D Data smoke test는 default domain을 suppress한 client를 사용한다.
