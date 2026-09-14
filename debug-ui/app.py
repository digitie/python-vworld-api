"""Streamlit 기반 VWorld REST 디버그 UI."""
# ruff: noqa: E402

from __future__ import annotations

import asyncio
import json
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd
import streamlit as st
from vworld_debug_ui.fixture_writer import jsonable, save_fixture
from vworld_debug_ui.history_store import append_history, load_recent_history
from vworld_debug_ui.preset_store import load_presets, save_preset

from vworld import (
    DATA_SERVICES,
    ApiCatalogEntry,
    ApiParameter,
    VworldClient,
    data_service_label,
    list_api_catalog,
    run_debug_function,
)
from vworld.debug import DebugRun

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
DATA_DIR = Path(__file__).resolve().parent / "data"
API_CATALOG = list_api_catalog()
CATALOG_BY_FUNCTION = {entry.function: entry for entry in API_CATALOG}


def main() -> None:
    st.set_page_config(page_title="VWorld REST Debug UI", layout="wide")
    _style()

    st.title("VWorld REST Debug UI")

    selected_entry, api_key, domain, timeout, preset_name, fixture_base_dir = _sidebar()
    client = VworldClient(
        api_key=api_key or None,
        domain=domain,
        timeout=timeout,
        retry_backoff=0,
    )

    _result_tabs(
        selected_entry,
        client,
        preset_name=preset_name,
        fixture_base_dir=fixture_base_dir,
    )


def _sidebar() -> tuple[ApiCatalogEntry, str, str | None, float, str, Path]:
    st.sidebar.header("Run settings")
    st.sidebar.selectbox("Data source", ("vworld",))
    selected_function = st.sidebar.selectbox(
        "API",
        options=tuple(CATALOG_BY_FUNCTION),
        format_func=lambda name: CATALOG_BY_FUNCTION[name].label,
    )
    selected_entry = CATALOG_BY_FUNCTION[selected_function]
    st.sidebar.caption("API full name")
    st.sidebar.write(_api_full_name(selected_entry))
    st.sidebar.caption(selected_entry.description)

    presets = load_presets(DATA_DIR / "presets", selected_function)
    preset_names = ["Default", *sorted(presets)]
    st.sidebar.subheader("Preset")
    preset_name = st.sidebar.selectbox("Preset", preset_names)

    default_key, default_domain = _default_client_settings()
    st.sidebar.subheader("Auth")
    api_key = st.sidebar.text_input(
        "API key",
        value=default_key,
        type="password",
        help=(
            "프로젝트 .env 또는 VWORLD_API_KEY를 기본값으로 읽습니다. "
            "복붙 공백은 호출 시 제거됩니다."
        ),
    )
    _service_key_links(selected_entry)

    st.sidebar.subheader("Domain")
    domain = st.sidebar.text_input(
        "Domain",
        value=default_domain,
        help="VWorld에 등록한 호출 도메인이 필요할 때 유지합니다.",
    )
    timeout = st.sidebar.number_input(
        "Timeout",
        min_value=1.0,
        max_value=60.0,
        value=10.0,
        step=1.0,
        help="API 요청 timeout seconds입니다.",
    )
    _history_panel(st.sidebar)
    fixture_base_dir = _fixture_base_dir_sidebar()
    return selected_entry, api_key, domain, float(timeout), preset_name, fixture_base_dir


def _result_tabs(
    selected_entry: ApiCatalogEntry,
    client: VworldClient,
    *,
    preset_name: str,
    fixture_base_dir: Path,
) -> None:
    raw_tab, parsed_tab, processed_tab, error_tab, trace_tab, fixture_tab = st.tabs(
        [
            "Raw Response",
            "Pydantic Model",
            "Processed Result",
            "Validation Errors",
            "Debug Trace",
            "Fixture / Testcase",
        ]
    )

    current_input: dict[str, Any] = {}
    with raw_tab:
        try:
            current_input = _raw_response_tab(selected_entry, client, preset_name=preset_name)
        except Exception as exc:
            st.error(f"Raw Response 실행 중 오류: {exc}")
    with parsed_tab:
        _pydantic_model_tab(selected_entry)
    with processed_tab:
        _processed_result_tab(selected_entry)
    with error_tab:
        _validation_errors_tab(selected_entry)
    with trace_tab:
        _debug_trace_tab(selected_entry, current_input)
    with fixture_tab:
        _fixture_tab(selected_entry, fixture_base_dir)


def _raw_response_tab(
    entry: ApiCatalogEntry,
    client: VworldClient,
    *,
    preset_name: str,
) -> dict[str, Any]:
    st.subheader(entry.label)
    st.caption(f"vworld / {entry.endpoint} / {entry.service} / {entry.request}")
    try:
        submitted, save_clicked, save_name, current_input, missing = _request_form(
            entry,
            preset_name,
        )
    except ValueError as exc:
        st.error(str(exc))
        return {}

    st.subheader("Request params preview")
    st.json(_preview_values(current_input), expanded=1)

    if save_clicked:
        if save_name.strip():
            save_preset(DATA_DIR / "presets", entry.function, save_name, current_input)
            st.success(f"Preset saved: {save_name}")
        else:
            st.error("Preset name을 입력하세요.")

    if submitted:
        if missing:
            st.error("필수 파라미터를 입력하세요: " + ", ".join(missing))
        else:
            with st.spinner("VWorld API 호출 중..."):

                async def invoke() -> DebugRun:
                    async with client:
                        return await run_debug_function(client, entry.function, current_input)

                debug_run = asyncio.run(invoke())
            st.session_state["last_run"] = debug_run
            append_history(DATA_DIR / "history", debug_run)

    debug_run = _current_run(entry)
    if debug_run is None:
        st.info("Run selected API를 누르면 원본 응답과 요청 metadata가 여기에 표시됩니다.")
        return current_input

    st.subheader("Raw body")
    st.json(debug_run.response.get("body", debug_run.response), expanded=2)
    st.caption("Request")
    st.json(debug_run.request, expanded=1)
    return current_input


def _request_form(
    entry: ApiCatalogEntry,
    preset_name: str,
) -> tuple[bool, bool, str, dict[str, Any], list[str]]:
    presets = load_presets(DATA_DIR / "presets", entry.function)
    preset = presets.get(preset_name, {}) if preset_name != "Default" else {}
    required_specs = [field for field in entry.parameters if field.required]
    optional_specs = [field for field in entry.parameters if not field.required]
    key_prefix = f"{entry.function}:{preset_name}"

    with st.form(f"request-form:{entry.function}"):
        st.subheader("Required parameters")
        required_values = _render_param_grid(
            required_specs,
            preset=preset,
            key_prefix=key_prefix,
            empty_message="이 API에 대해 로컬에 정리된 필수 파라미터 명세가 없습니다.",
        )

        st.subheader("Optional parameters")
        optional_values = _render_param_grid(
            optional_specs,
            preset=preset,
            key_prefix=key_prefix,
        )

        extra_text = st.text_area(
            "Extra params JSON",
            value="{}",
            height=110,
            help="폼에 없는 provider 파라미터를 JSON object로 추가합니다.",
            key=f"{key_prefix}:extra",
        )
        save_name = st.text_input(
            "Preset name",
            value="",
            key=f"{key_prefix}:preset-name",
        )
        save_col, run_col = st.columns([0.35, 0.65])
        with save_col:
            save_clicked = st.form_submit_button(
                "Save preset",
                use_container_width=True,
            )
        with run_col:
            submitted = st.form_submit_button(
                "Run selected API",
                type="primary",
                use_container_width=True,
            )

    values = {**required_values, **optional_values, **_parse_extra_params(extra_text)}
    missing = [field.name for field in required_specs if _is_missing(values.get(field.name))]
    return submitted, save_clicked, save_name, values, missing


def _render_param_grid(
    specs: list[ApiParameter],
    *,
    preset: dict[str, Any],
    key_prefix: str,
    empty_message: str | None = None,
) -> dict[str, Any]:
    if not specs:
        if empty_message:
            st.caption(empty_message)
        return {}

    values: dict[str, Any] = {}
    for index in range(0, len(specs), 2):
        columns = st.columns(2)
        for column, field in zip(columns, specs[index : index + 2], strict=False):
            with column:
                default = preset.get(field.name, field.default)
                values[field.name] = _field_widget(
                    field,
                    default,
                    key=f"{key_prefix}:param:{field.name}",
                )
    return values


def _field_widget(field: ApiParameter, default: Any, *, key: str) -> Any:
    help_text = field.description or None
    if field.kind == "data_service":
        return _data_service_widget(field, default, key=key)
    if field.kind == "select":
        index = field.choices.index(str(default)) if str(default) in field.choices else 0
        return st.selectbox(field.label, field.choices, index=index, help=help_text, key=key)
    if field.kind == "checkbox":
        return st.checkbox(field.label, value=bool(default), help=help_text, key=key)
    if field.kind == "number":
        return st.number_input(
            field.label,
            value=_int_default(default, field.default),
            step=1,
            help=help_text,
            key=key,
        )
    return st.text_input(
        field.label,
        value="" if default is None else str(default),
        help=help_text,
        key=key,
    )


def _data_service_widget(field: ApiParameter, default: Any, *, key: str) -> str:
    default_id = str(default or field.default).upper()
    selected_index = 0
    for index, service in enumerate(DATA_SERVICES):
        if service.service_id.upper() == default_id:
            selected_index = index
            break
    selected = st.selectbox(
        field.label,
        DATA_SERVICES,
        index=selected_index,
        format_func=data_service_label,
        help=field.description or None,
        key=key,
    )
    st.caption(f"{selected.category} · {selected.provider} · updated {selected.updated_at}")
    return selected.service_id


def _pydantic_model_tab(entry: ApiCatalogEntry) -> None:
    debug_run = _current_run(entry)
    if debug_run is None:
        st.info("Raw Response 탭에서 선택한 API를 실행하면 여기에서 Pydantic 모델을 확인합니다.")
        return
    _show_json(jsonable(debug_run.parsed), expanded=2)


def _processed_result_tab(entry: ApiCatalogEntry) -> None:
    debug_run = _current_run(entry)
    if debug_run is None:
        st.info("Raw Response 탭에서 API를 실행하면 처리된 row preview를 표시합니다.")
        return
    processed = jsonable(debug_run.processed)
    _show_json(processed, expanded=2)
    items = processed.get("items", []) if isinstance(processed, dict) else []
    if items:
        st.dataframe(pd.json_normalize(items, sep="."), use_container_width=True)


def _validation_errors_tab(entry: ApiCatalogEntry) -> None:
    debug_run = _current_run(entry)
    if debug_run is None:
        st.info("아직 실행된 API가 없습니다.")
        return
    if debug_run.error:
        st.error(debug_run.error.get("message", "Error"))
        st.json(debug_run.error, expanded=1)
        return
    st.success("현재 실행 결과에서 validation error가 없습니다.")


def _debug_trace_tab(entry: ApiCatalogEntry, current_input: dict[str, Any]) -> None:
    st.subheader("Catalog")
    st.dataframe(
        pd.DataFrame(_api_catalog_rows()),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Selected API")
    st.json(jsonable(entry), expanded=1)
    st.link_button("서비스키 발급받기", entry.auth_key_url)

    selected_service = _selected_data_service(entry, current_input)
    if selected_service is not None:
        st.subheader("Dataset catalog")
        st.caption(data_service_label(selected_service))
        st.dataframe(
            pd.DataFrame([jsonable(selected_service)]),
            use_container_width=True,
            hide_index=True,
        )

    debug_run = _current_run(entry)
    if debug_run is None:
        return
    st.subheader("Trace")
    for trace_entry in debug_run.trace:
        st.write(f"- {trace_entry}")


def _fixture_tab(entry: ApiCatalogEntry, fixture_base_dir: Path) -> None:
    debug_run = _current_run(entry)
    if debug_run is None:
        st.info("Raw Response 탭에서 선택한 API를 실행하면 fixture 저장 폼이 표시됩니다.")
        st.caption("Fixture base dir")
        st.code(str(fixture_base_dir), language=None)
        return
    _fixture_panel(debug_run, fixture_base_dir)


def _fixture_panel(debug_run: DebugRun, fixture_base_dir: Path) -> None:
    st.subheader("Save as fixture")
    st.caption("Fixture base dir")
    st.code(str(fixture_base_dir), language=None)
    with st.form(f"fixture-{debug_run.function}"):
        case_name = st.text_input("Case name", value=f"{debug_run.function}_normal")
        description = st.text_area("Description", value="")
        assertion_mode = st.selectbox(
            "Assertion mode",
            ("snapshot", "schema_only", "required_fields"),
        )
        exclude_fields_raw = st.text_input(
            "Exclude fields",
            value="fetched_at, request_id, updated_at",
        )
        required_fields_raw = st.text_input("Required fields", value="")
        overwrite = st.checkbox("Overwrite existing fixture", value=False)
        preview = st.checkbox("Show fixture preview", value=True)
        save_clicked = st.form_submit_button("Save as fixture", type="primary")

    assertion = {
        "mode": assertion_mode,
        "exclude_fields": _csv_values(exclude_fields_raw),
        "required_fields": _csv_values(required_fields_raw),
    }
    if preview:
        st.json(
            {
                "name": case_name,
                "function": debug_run.function,
                "input": debug_run.input,
                "request": debug_run.request,
                "response": debug_run.response,
                "processed": jsonable(debug_run.processed),
                "assertion": assertion,
            },
            expanded=1,
        )
    if save_clicked:
        try:
            path = save_fixture(
                base_dir=fixture_base_dir,
                function_name=debug_run.function,
                case_name=case_name,
                description=description,
                input_data=debug_run.input,
                request_data=debug_run.request,
                response_data=debug_run.response,
                parsed_result=debug_run.parsed,
                processed_result=debug_run.processed,
                assertion=assertion,
                library_version=_library_version(),
                overwrite=overwrite,
            )
        except FileExistsError as exc:
            st.error(str(exc))
        else:
            st.success(f"Saved: {_display_path(path)}")


def _history_panel(target: Any = st) -> None:
    target.subheader("History")
    rows = load_recent_history(DATA_DIR / "history", limit=8)
    if not rows:
        target.caption("No recent runs.")
        return
    for row in rows:
        status = "OK" if row.get("error") is None else "ERROR"
        function_name = str(row.get("function"))
        catalog = CATALOG_BY_FUNCTION.get(function_name)
        target.markdown(f"**{catalog.label if catalog else function_name}** · {status}")
        target.caption(str(row.get("created_at", "")))


def _api_full_name(entry: ApiCatalogEntry) -> str:
    return f"{entry.label} / {entry.endpoint} / {entry.service} / {entry.request}"


def _api_catalog_rows() -> list[dict[str, str]]:
    return [
        {
            "function": entry.function,
            "label": entry.label,
            "endpoint": entry.endpoint,
            "service": entry.service,
            "request": entry.request,
            "version": entry.version,
            "parameters": ", ".join(field.name for field in entry.parameters),
            "description": entry.description,
        }
        for entry in API_CATALOG
    ]


def _service_key_links(entry: ApiCatalogEntry) -> None:
    st.sidebar.caption("Service key links")
    st.sidebar.link_button(
        "서비스키 발급받기",
        entry.auth_key_url,
        use_container_width=True,
    )


def _fixture_base_dir_sidebar() -> Path:
    st.sidebar.subheader("Fixtures")
    options = [str(path) for path in _fixture_dir_candidates()]
    custom_label = "Custom..."
    selected = st.sidebar.selectbox("Fixture base dir", [*options, custom_label])
    if selected == custom_label:
        selected = st.sidebar.text_input(
            "Custom fixture base dir",
            value=str(FIXTURE_DIR.resolve()),
        )
    st.sidebar.caption(selected)
    return Path(selected)


def _fixture_dir_candidates() -> list[Path]:
    preferred = [
        FIXTURE_DIR,
        REPO_ROOT / "tests",
        Path(__file__).resolve().parent,
        REPO_ROOT,
    ]
    candidates: list[Path] = []
    for path in preferred:
        resolved = path.resolve()
        if resolved not in candidates:
            candidates.append(resolved)
    return candidates


def _selected_data_service(
    entry: ApiCatalogEntry,
    current_input: dict[str, Any],
) -> Any | None:
    if entry.function != "get_data_feature":
        return None
    selected_id = str(current_input.get("data") or "").strip().upper()
    if not selected_id:
        return None
    for service in DATA_SERVICES:
        if service.service_id.upper() == selected_id:
            return service
    return None


def _current_run(entry: ApiCatalogEntry) -> DebugRun | None:
    run = st.session_state.get("last_run")
    if not isinstance(run, DebugRun):
        return None
    if run.function != entry.function:
        return None
    return run


def _parse_extra_params(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Extra params JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Extra params JSON must be an object")
    blocked = {"key", "serviceKey", "ServiceKey", "apiKey", "authKey"}
    return {str(key): value for key, value in payload.items() if str(key) not in blocked}


def _preview_values(values: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, bool):
            result[key] = value
        elif value is None:
            continue
        elif str(value).strip():
            result[key] = value
    return jsonable(result)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    return str(value).strip() == ""


def _int_default(value: Any, fallback: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback or 0)


def _csv_values(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def _show_json(value: Any, *, expanded: int) -> None:
    if value is None:
        st.info("No JSON value to display.")
        return
    st.json(value, expanded=expanded)


def _default_client_settings() -> tuple[str, str]:
    client = VworldClient.from_env_file(REPO_ROOT / ".env", retry_backoff=0)
    return client.api_key or "", client.domain or ""


def _library_version() -> str | None:
    try:
        return metadata.version("python-vworld-api")
    except metadata.PackageNotFoundError:
        return None


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _style() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f7f9fc; color: #1e293b; }
        [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e2e8f0; }
        div[data-testid="stForm"] {
          background: #ffffff;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 16px;
        }
        .stTabs [data-baseweb="tab-list"] { gap: 4px; }
        .stTabs [data-baseweb="tab"] {
          border-radius: 8px 8px 0 0;
          padding: 8px 12px;
          font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
