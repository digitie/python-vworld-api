# Test

기본 test suite는 live VWorld service를 호출하지 않는다. HTTP test와 정확한 URL/query assertion에는 `tests/conftest.py`의 local `httpx.MockTransport` helper를 사용한다.

## 문서 언어 정책

이 저장소의 모든 Markdown/RST 문서는 한글로 작성한다. 공식 API field, code identifier, 명령어, URL, provider 원문은 필요한 경우 원문을 유지한다.

## 필수 확인

```bash
python -m compileall src/vworld tests
python -m pytest
python -m ruff check .
python -m mypy src/vworld
```

## Test strategy

- Parameter test는 bool conversion, CSV join, bbox/point formatting, invalid size를 다룬다.
- HTTP test는 key injection, JSON parsing, VWorld error code mapping, `NOT_FOUND`, binary JSON error payload, retry, network timeout을 다룬다.
- 비동기 테스트는 `VworldClient`의 async 문맥 종료와 명시적 빈 domain 보존을 다룬다.
- REST client test는 `version=2.0`과 endpoint별 required parameter를 assert한다.
- OGC test는 WMS/WFS uppercase parameter name과 response wrapper를 assert한다.
- Image/tile test는 StaticMap, legend, WMTS, TMS URL shape를 assert한다.
- Catalog test는 공식 158-entry count와 모든 entry의 2.0 여부를 assert한다.
- Pagination test는 `response.page` traversal, item extraction, loop guard를 다룬다.
- Metadata test는 query `key=`와 WMTS/TMS path key redaction을 다룬다.
- Debug UI fixture test는 민감값 redaction과 overwrite protection을 확인한다.
- Generated fixture replay test는 `tests/fixtures/**/*.json`을 load해 저장된 raw response를 parse하고 processor를 실행하며 live network를 호출하지 않는다.
- Catalog test는 debug API catalog entry, service key issuance URL, 사람이 읽을 수 있는 data service label을 다룬다.
- REST client test는 붙여넣은 VWorld service key의 whitespace normalization을 확인한다.

## Live test

Live test는 opt-in이어야 한다.

- `@pytest.mark.live`를 붙인다.
- `VWORLD_API_KEY`가 없으면 skip한다.
- Private key나 key가 포함된 query URL을 raw response에 저장하지 않는다.
- 하나의 geocoder call 또는 작은 StaticMap 같은 작은 request를 선호한다.
- Endpoint별 VWorld key/domain rejection은 live-only smoke에서는 skip할 수 있지만 Search/Geocoder와 async Search는 usable key로 통과해야 한다.

기본 validation path에는 현재 live test가 필요하지 않다.

## Fixture replay

Debug UI fixture는 `tests/fixtures/{function}/{case}.json`에 저장한다. Common runner인 `tests/test_generated_fixtures.py`는 각 `function`을 `tests/runners.py`의 parser/processor callable에 mapping한다.

지원 assertion mode:

- `snapshot`: `assertion.exclude_fields`에 있는 key를 제외하고 processed output 비교
- `schema_only`: parsing과 processing 완료 여부 확인
- `required_fields`: dot-separated field가 processed output에 존재하는지 확인

Fixture에는 VWorld API key, Authorization header, access token, refresh token, tile path key를 저장하지 않는다. Debug UI writer는 `input`, `request`, `response`, `parsed`, `processed` 모든 필드의 민감값을 JSON을 쓰기 전에 mask한다. History store도 동일한 마스킹을 적용한다.

## 현재 live verification

Live smoke suite는 `tests/test_live_api.py`에 있다.

Local `.env` 또는 exported environment variable로 실행한다.

```bash
python -m pytest -m live
```

권장 local `.env`:

```bash
VWORLD_API_KEY="issued-key"
VWORLD_DOMAIN="registered-domain"
```

VWorld endpoint별 domain 동작은 균일하지 않다. 2026-05-06 local verification에서 Search, Geocoder, image, WMTS, TMS는 발급 key로 동작했다. WMS/WFS capabilities는 명시적 blank `domain=` query가 가장 안정적이었고, 2D Data smoke test는 default domain을 suppress한 client를 사용했다. VWorld는 같은 key와 request shape에도 간헐적으로 `INCORRECT_KEY`를 반환할 수 있으므로 live test는 짧은 smoke call을 retry한다.
