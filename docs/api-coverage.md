# API coverage

이 문서는 현재 `vworld`가 어떤 VWorld API를 구현했는지, 무엇을 의도적으로 제외했는지 기록한다.

## 문서 언어 정책

이 저장소의 모든 Markdown/RST 문서는 한글로 작성한다. 공식 API field, code identifier, 명령어, URL, provider 원문은 필요한 경우 원문을 유지한다.

## 구현됨

| Area | Endpoint | Version rule | Method |
|---|---|---|---|
| Search | `https://api.vworld.kr/req/search` | 2.0 only | `search*` |
| Geocoder | `https://api.vworld.kr/req/address` | 2.0 only | `get_coord`, `get_address` |
| 2D Data | `https://api.vworld.kr/req/data` | 2.0 only | `get_data_feature`, `get_data_feature_type` |
| WMS | `https://api.vworld.kr/req/wms` | VWorld 2.0 reference, OGC WMS 1.3.0 | `wms_get_capabilities`, `wms_get_map`, `wms_get_feature_info` |
| WFS | `https://api.vworld.kr/req/wfs` | VWorld 2.0 reference, OGC WFS 1.1.0 | `wfs_get_capabilities`, `wfs_describe_feature_type`, `wfs_get_feature` |
| Legend Image | `https://api.vworld.kr/req/image` | 2.0 only | `get_legend_graphic`, `get_legend_style` |
| StaticMap | `https://api.vworld.kr/req/image` | 2.0 only | `static_map`, `static_map_url` |
| WMTS | `/req/wmts/1.0.0/{key}/...` | official WMTS path only | `wmts_*` |
| TMS | `/req/tms/1.0.0/{key}/...` | official TMS path only | `tms_*` |

## Public type

Public wrapper는 원래 문자열 값과 이 패키지가 제공하는 typed helper를 모두 받는다. Enum은 search/address category, CRS, legend type, image format, StaticMap basemap, tile layer 같은 문서화된 parameter set을 다룬다. `LatLon`, `LonLat`, `BBox`, `BinaryResponse`, `TextResponse`는 frozen Pydantic v2 model이므로 외부 program은 기존 tuple input을 바꾸지 않고 `model_validate()`, `model_dump()`, JSON schema generation을 사용할 수 있다.

외부 장소/주소 DTO는 공개 입력 계약에 포함하지 않는다. 특히 `python-kraddr-base`의 `PlaceCoordinate`, `Address`는 import하지 않고, 함수 내부에서도 중간 값 객체로 만들지 않는다. 외부 앱은 필요한 값을 문자열 주소, VWorld `x,y` 문자열, `(lon, lat)` 튜플, 또는 `LatLon`/`LonLat`로 변환한 뒤 호출한다.

## HTTP runtime

HTTP 계층은 `httpx.AsyncClient`를 사용한다. `VworldClient` 하나로 REST, OGC, 이미지, 타일과 페이지 순회를 비동기로 제공한다. 각 요청·재시도·리다이렉트는 공통 AsyncTokenBucket을 거치며 오류 매핑은 `_http.py`에서 수행한다. URL 빌더와 순수 파싱·메타데이터 함수는 일반 함수다.

## General-purpose helper

- `iter_search_pages` / `iter_search_items`: Search API `response.page` metadata를 따른다.
- `iter_data_feature_pages` / `iter_data_feature_items`: 2D Data `GetFeature`에 같은 pagination pattern을 적용한다.
- `response_page_info`, `has_next_page`, `next_page_no`, `response_items`: 문서화된 `response.record`, `response.page`, `response.result.items` 구조를 정규화한다.
- `VworldResponseMetadata`, `sanitize_request_params`, `request_params_from_url`, `redact_credentials_in_text`, `make_cache_key`: `key=` query 값과 WMTS/TMS path key를 유출하지 않는 logging/cache integration helper다.
- `DebugRun`, `run_debug_function`, `debug_search`, `debug_geocode`, `debug_reverse_geocode`, `debug_get_data_feature`: fixture 생성을 위한 Streamlit-independent debug run을 제공한다.
- `parse_*_response`, `process_*_response`: `tests/test_generated_fixtures.py`가 사용하는 replay path다.
- `list_api_catalog`, `get_api_catalog_entry`, `data_service_label`: VWorld service key 발급 link와 사람이 읽을 수 있는 2D data service label을 포함한 작은 library-side catalog다.

## 구현하지 않음

다음 항목은 Python HTTP endpoint wrapper가 아니다.

- 2D지도 API JavaScript SDK
- WebGL 3D지도 JavaScript SDK
- 3D분석ㆍ시뮬레이션 JavaScript SDK
- 2D/3D 모바일 SDK reference
- 3D 데스크톱 SDK reference
- 배경지도 API 1.0, 벡터지도 API 1.0

향후 VWorld page가 이 영역의 안정 HTTP endpoint를 공개하면 일반 method로 추가하고 공식 URL과 함께 이 문서를 갱신한다.

## 2D Data catalog

- 공식 list count: 158 entries
- Generated date: 2026-05-01
- Code: `src/vworld/catalog.py`
- Markdown: `docs/data-services.md`

모든 catalog entry는 `version == "2.0"`이다. Test는 count와 sentinel ID를 assert해 accidental truncation을 잡는다.
