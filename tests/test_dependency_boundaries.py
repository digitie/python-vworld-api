from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_dependencies_do_not_include_kraddr_base() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "python-kraddr-base" not in pyproject


def test_package_import_does_not_load_kraddr_base() -> None:
    import vworld  # noqa: F401

    assert "kraddr" not in sys.modules
    assert "kraddr_base" not in sys.modules


def test_source_does_not_expose_kraddr_base_types() -> None:
    source_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (PROJECT_ROOT / "src" / "vworld").rglob("*.py")
    )

    assert "python-kraddr-base" not in source_text
    assert "kraddr.base" not in source_text
    assert "kraddr_base" not in source_text
    assert "PlaceCoordinate" not in source_text
