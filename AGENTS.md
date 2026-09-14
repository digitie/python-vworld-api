# AGENTS

## 역할

이 저장소(GitHub 이름 `python-vworld-api`, Python 패키지 `vworld`)는 VWorld REST, OGC, 정적 이미지, WMTS/TMS API를 래핑하는 **비공식 Python 클라이언트 라이브러리**다. `VworldClient` 하나로 native async 호출을 제공하며, 디버그 UI는 `debug-ui/` 하위 패키지로 운영한다.

## 식별자 (혼동 방지)

| 항목 | 값 |
|------|----|
| GitHub 저장소 이름 | `python-vworld-api` |
| Python import | `from vworld import VworldClient` |
| 환경변수 prefix | `VWORLD_*` |
| 디버그 UI 패키지 | `debug-ui/` (Streamlit) |

## 문서 언어 정책

이 저장소의 모든 Markdown/RST 문서는 한글로 작성한다. 공식 API 필드명, 코드 식별자, 명령어, URL, provider 원문처럼 그대로 보존해야 하는 값만 영어를 유지한다. 새 문서나 기존 문서를 수정할 때도 이 규칙을 우선한다.

## 지시 우선순위

1. 사용자 요청
2. 이 `AGENTS.md`
3. `SKILL.md`
4. `docs/` 아래 문서
5. `README.md`
6. 기존 코드와 테스트
7. 최소한의, 되돌릴 수 있는 가정

## 먼저 읽을 것

작업 전에 반드시 다음을 읽는다:

1. `README.md` — 프로젝트 개요와 빠른 시작
2. `SKILL.md` — DO NOT 룰, 불변 조건, 도메인 어휘
3. `docs/resume.md` — 현재 진척도와 "다음 한 작업"
4. `docs/decisions.md` — 관련 ADR
5. `docs/repeated-mistakes.md` — 반복 실수 목록

## 절대 하지 말 것 (DO NOT)

1. **API key 평문 커밋 금지** — fixture, history, 로그에서 반드시 `redact_sensitive()`로 마스킹한다.
2. **Sync/Async 로직 분기 금지** — validation과 param 조립은 모듈 레벨 공유 함수(`_make_*_params`)를 사용한다. 한쪽만 수정하는 실수를 방지한다.
3. **단순 전달용 wrapper 금지** — 불필요한 얇은 wrapper, 장기 호환 alias, 임시 facade를 만들지 않는다.
4. **HTTP 오류 매핑 분산 금지** — `src/vworld/_http.py`에만 둔다.
5. **1.0 API 구현 금지** — VWorld 2.0만 구현한다.
6. **테스트에서 라이브 네트워크 호출 금지** — `@pytest.mark.live`가 아닌 기본 테스트는 offline이어야 한다.
7. **문서에 절대 경로 금지** — 프로젝트 기준 상대 경로만 사용한다.
8. **SDK 문서 래핑 금지** — JavaScript, 모바일, 데스크톱 SDK는 HTTP 함수 래핑 대상이 아니다.

## 구현 원칙

- 공식 VWorld 문서를 먼저 확인한다.
- REST 계열은 기본 `version=2.0`, `format=json`, `errorformat=json`을 유지한다.
- 공개 메서드는 파라미터 검증과 URL/요청 조립에 집중한다.
- downstream이 직접 사용할 안정된 public client, typed model, enum, helper를 제공한다.
- 외부 API 관련 작업은 wrapper/adapter/gateway 지양 원칙을 먼저 확인하고 문서/코드에 반영한 뒤 진행한다.
- TripMate나 `python-krtour-map`에서 필요한 계약이 부족하면 이 저장소의 public API를 먼저 안정화한다.

## 테스트 규칙

- 기본 테스트는 라이브 네트워크를 호출하지 않는다.
- 새 엔드포인트 메서드를 추가하면 happy path, 잘못된 파라미터, 오류 응답 테스트를 추가한다.
- URL 경로에 키가 들어가는 WMTS/TMS는 쿼리 `key=`를 붙이지 않는지 반드시 확인한다.
- 카탈로그를 갱신하면 `len(DATA_SERVICES)` 테스트와 `docs/data-services.md`도 함께 갱신한다.
- `HttpxMock`에 등록한 route는 teardown에서 전량 소비를 검증한다.

## 문서 규칙

- 구현 범위는 `docs/api-coverage.md`에 갱신한다.
- 반복 실수는 `docs/repeated-mistakes.md`에 남긴다.
- 사용자 예시는 README에 짧고 실행 가능한 형태로 둔다.
- Python docstring과 주석도 한글로 작성한다.

## 작업 후 체크리스트

- [ ] `python -m pytest` 통과
- [ ] `python -m ruff check .` 통과
- [ ] `python -m mypy src/vworld` 통과
- [ ] `docs/journal.md`에 작업 항목 추가 (역시간순)
- [ ] `docs/resume.md`의 진척도 갱신
- [ ] 의사결정이 있었다면 `docs/decisions.md`에 ADR 추가
- [ ] 사용자 가시 변경이면 `CHANGELOG.md` 갱신

## 검증

```bash
python -m compileall src/vworld tests
python -m pytest
python -m ruff check .
python -m mypy src/vworld
```


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
