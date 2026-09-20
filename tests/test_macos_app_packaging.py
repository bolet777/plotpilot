"""Smoke checks for macOS app packaging sources (no PyInstaller run in CI by default)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_macos_packaging_files_exist() -> None:
    assert (REPO / "packaging/macos/entry.py").is_file()
    assert (REPO / "packaging/macos/plotpilot.spec").is_file()
    assert (REPO / "scripts/build_macos_app.sh").is_file()
    assert (REPO / "assets/icons/plotpilot.icns").is_file()


def test_build_script_is_executable() -> None:
    mode = (REPO / "scripts/build_macos_app.sh").stat().st_mode
    assert mode & 0o111
