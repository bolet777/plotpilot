"""Smoke tests for project wiring (no hardware, no GUI event loop)."""

from __future__ import annotations

from plotpilot import __version__


def test_version_is_semantic_placeholder() -> None:
    assert __version__ == "0.1.0"


def test_main_window_importable() -> None:
    from plotpilot.ui.main_window import MainWindow

    assert MainWindow is not None
