"""Smoke checks for macOS app packaging sources (no PyInstaller run in CI by default)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_macos_packaging_files_exist() -> None:
    assert (REPO / "lance.sh").is_file()
    assert (REPO / "packaging/macos/entry.py").is_file()
    assert (REPO / "packaging/macos/plotpilot.spec").is_file()
    assert (REPO / "scripts/build_macos_app.sh").is_file()
    assert (REPO / "assets/icons/plotpilot.icns").is_file()


def test_build_script_is_executable() -> None:
    for path in (REPO / "lance.sh", REPO / "scripts/build_macos_app.sh"):
        assert path.stat().st_mode & 0o111
