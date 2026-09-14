# python-vworld-api

VWorld(브이월드) HTTP API를 Python에서 쓰기 쉽게 감싼 비공식 클라이언트입니다.

이 패키지는 VWorld 공식 [API 레퍼런스](https://www.vworld.kr/dev/v4apiRefer.do)를 기준으로, Python에서 직접 호출 가능한 REST/OGC/타일 엔드포인트를 함수로 제공합니다. 1.0과 2.0 문서가 함께 있는 API는 2.0만 구현했습니다.

## 특징

- 검색 API 2.0: 장소, 주소, 행정구역, 도로명 검색
- Geocoder API 2.0: 주소 좌표 변환, 좌표 주소 변환
- 2D데이터 API 2.0: `GetFeature`, `GetFeatureType`, 공식 서비스 ID 158건 카탈로그
- WMS/WFS API 2.0 레퍼런스: `GetCapabilities`, `GetMap`, `GetFeatureInfo`, `DescribeFeatureType`, `GetFeature`
- 범례이미지/StaticMap API 2.0: 이미지 바이트 응답과 URL 빌더
- WMTS/TMS: 타일, 해외위성영상 테마 타일, capabilities/resource URL
- `httpx.AsyncClient` 기반 native async `VworldClient`와 공통 TPS 제어
- 페이지 반복/아이템 추출 헬퍼와 인증키를 제거한 메타데이터/캐시 키 유틸
- 네트워크 없이 검증되는 fixture/mock 기반 테스트

JS 지도 SDK, WebGL 3D 지도 SDK, 모바일/데스크톱 SDK는 Python HTTP 엔드포인트가 아니라 런타임 SDK 문서이므로 이 패키지의 함수 래핑 범위에서 제외했습니다. 범위와 근거는 [docs/api-coverage.md](docs/api-coverage.md)에 정리했습니다.

## 설치

```bash
pip install python-vworld-api
```

개발 중인 로컬 저장소에서는:

```bash
pip install -e ".[dev]"
```

## 인증키

VWorld 인증키를 환경변수에 넣습니다.

```bash
export VWORLD_API_KEY="발급받은_인증키"
```

PowerShell:

```powershell
$env:VWORLD_API_KEY="발급받은_인증키"
```

도메인 파라미터가 필요한 환경에서는 `VWORLD_DOMAIN`, `VworldClient.from_env_file()`, 또는 클라이언트 생성자의 `domain=`을 사용합니다. 엔드포인트별로 VWorld의 도메인 검증 동작이 다를 수 있어, 특정 호출에서만 바꾸려면 메서드의 `domain=` 인자를 사용합니다.

## 사용 예시

```python
import asyncio
from vworld import VworldClient


async def main() -> None:
    async with VworldClient.from_env() as client:

        result = (await client.search_address("성남시 분당구 판교로 242"))
        print(result["response"]["result"]["items"])

        coord = (await client.geocode("판교로 242", type="road"))
        print(coord["response"]["result"]["point"])

        reverse = (await client.reverse_geocode((127.101313354, 37.402352535), type="both"))
        print(reverse["response"]["result"])


asyncio.run(main())
```

모든 네트워크 호출에 `await`를 사용합니다. `async with`가 내부 HTTP 세션을 정리합니다.

```python
import asyncio
from vworld import VworldClient


async def main() -> None:
    async with VworldClient.from_env_file() as client:
        result = await client.search_address("성남시 분당구 판교로 242", size=1)
        print(result["response"]["result"]["items"])


asyncio.run(main())
```

로컬 `.env` 파일에서 바로 읽을 수도 있습니다. `.env`는 `.gitignore`에 포함되어 커밋되지 않습니다.

```bash
VWORLD_API_KEY="발급받은_인증키"
VWORLD_DOMAIN="인증키에 등록한_도메인"
```

```python
client = VworldClient.from_env_file()
```

## 타입/좌표 모델

외부 프로그램에서 문자열 상수를 직접 외우지 않아도 되도록 주요 파라미터 enum을 제공합니다. 기존 문자열 호출은 그대로 동작합니다. 공개 값 객체는 Pydantic v2 `BaseModel` 기반이라 `model_validate()`, `model_dump()`, `model_json_schema()`로도 다룰 수 있습니다.

```python
import asyncio
from vworld import (
    AddressCategory,
    AddressType,
    Crs,
    ImageFormat,
    SearchType,
    StaticMapBase,
    VworldClient,
    bbox_from_latlon,
    latlon,
)


async def main() -> None:
    async with VworldClient.from_env_file() as client:

        (await client.search(
            "판교",
            SearchType.ADDRESS,
            category=AddressCategory.ROAD,
            bbox=bbox_from_latlon(south=37.3, west=126.9, north=37.6, east=127.2),
            crs=Crs.WGS84,
        ))

        (await client.geocode("판교로 242", type=AddressType.ROAD))
        (await client.reverse_geocode(latlon(37.402352535, 127.101313354)))

        client.static_map_url(
            center=latlon(37.566643, 126.978271),
            zoom=16,
            size=(400, 400),
            basemap=StaticMapBase.PHOTO_HYBRID,
            format=ImageFormat.PNG,
        )

        payload = latlon(37.402352535, 127.101313354).model_dump()


asyncio.run(main())
```

VWorld의 `point` 파라미터는 `x,y` 순서입니다. `EPSG:4326`에서는 `x=lon`, `y=lat`이므로 일반적인 “위경도” 입력은 `latlon(lat, lon)` 또는 `LatLon(lat=..., lon=...)`을 쓰는 것을 권장합니다. 기존 `(lon, lat)` 튜플도 계속 지원합니다.

`python-kraddr-base`의 `PlaceCoordinate`, `Address` 같은 외부 DTO는 런타임 의존성이나 입력 계약에 포함하지 않습니다. 외부 앱 경계에서 받은 장소/주소 객체는 이 패키지로 넘기기 전에 문자열 주소, VWorld `x,y` 문자열, `(lon, lat)` 튜플, 또는 이 패키지의 `LatLon`/`LonLat` 값 객체로 변환하세요.

`StaticMapBase`와 `ImageFormat`은 공식 문서의 값(`NONE`, `GRAPHIC_WHITE`, `GRAPHIC_NIGHT`, `PHOTO_HYBRID`, `bmp` 등)을 포함합니다. 기존에 쓰기 쉬운 이름으로 넣었던 `StaticMapBase.HYBRID`는 `PHOTO_HYBRID` 별칭으로 유지합니다.

2D 데이터 API:

```python
import asyncio
from vworld import VworldClient, get_data_service


async def main() -> None:
    async with VworldClient.from_env(domain="example.com") as client:
        service = get_data_service("LT_C_ADEMD_INFO")

        features = (await client.get_data_feature(
            service.service_id,
            attr_filter="emd_cd:=:11650108",
            geometry=False,
            columns=["emd_cd", "full_nm"],
        ))
        print(features["response"]["result"])

        async for item in client.iter_data_feature_items(
            service.service_id,
            attr_filter="emd_cd:=:11650108",
            geometry=False,
            size=1000,
            max_pages=3,
        ):
            print(item)


asyncio.run(main())
```

응답을 직접 다루는 코드에서는 `response_items()`와 `response_page_info()`로
VWorld의 `response.result.items`, `response.page`, `response.record` 구조를
일관되게 읽을 수 있습니다. 로그나 캐시 키에는 `sanitize_request_params()`와
`make_cache_key()`를 쓰면 `key=` 값이 섞이지 않습니다.

WMS/WFS:

```python
import asyncio
from vworld import VworldClient


async def main() -> None:
    async with VworldClient.from_env() as client:
        image = await client.wms_get_map(
            layers=["lp_pa_cbnd_bonbun", "lp_pa_cbnd_bubun"],
            styles=["lp_pa_cbnd_bonbun_line", "lp_pa_cbnd_bubun_line"],
            bbox=(14133818.022824, 4520485.8511757, 14134123.770937, 4520791.5992888),
            width=256,
            height=256,
        )
        print(image.content_type, len(image.content))

        gml = await client.wfs_get_feature(
            "lt_c_uq111",
            bbox=(13987670, 3912271, 14359383, 4642932),
            property_name=["mnum", "sido_cd", "sigungu_cd", "ag_geom"],
            max_features=40,
        )
        print(gml.text[:200])


asyncio.run(main())
```

타일 URL:

```python
from vworld import VworldClient

client = VworldClient.from_env()
url = client.wmts_tile_url("Base", 11, 793, 1746)
print(url)
# https://api.vworld.kr/req/wmts/1.0.0/{key}/Base/11/793/1746.png
```

## 개발 검증

```bash
python -m compileall src/vworld tests
python -m pytest
python -m ruff check .
python -m mypy src/vworld
```

자세한 테스트 기준은 [docs/testing.md](docs/testing.md)를 참고하세요.

## 디버그 UI와 fixture replay

`debug-ui/`에는 Streamlit 기반 디버깅 웹툴이 있습니다. 라이브 REST 호출을 실행해 Raw Response, Pydantic Model, Processed Result, Validation Errors를 나눠 보고, 의미 있는 케이스를 `tests/fixtures/{function}/{case}.json`으로 저장합니다.

```bash
pip install -e ".[dev]"
cd debug-ui
pip install -e .
streamlit run app.py
```

저장된 fixture는 `tests/test_generated_fixtures.py`가 자동으로 읽어 replay 방식으로 검증하므로 기본 테스트는 네트워크를 호출하지 않습니다. 자세한 구조는 [docs/debug-ui.md](docs/debug-ui.md)를 참고하세요.

Debug UI는 프로젝트 루트 `.env`의 `VWORLD_API_KEY`, `VWORLD_DOMAIN`을 기본값으로 읽습니다. 서비스키를 복사/붙여넣기하면서 들어간 공백과 줄바꿈은 클라이언트 생성 시 제거됩니다.


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
