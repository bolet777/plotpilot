"""Optional physical-device smoke tests (never run by default)."""

from __future__ import annotations

import shutil

import pytest

from plotpilot.plotter.axidraw import AxiDrawCliBackend


@pytest.mark.hardware
def test_axidraw_list_names_when_connected() -> None:
    """Passive probe only — no pen or XY motion. Skips when axicli or hardware is absent."""
    if shutil.which("axicli") is None:
        pytest.skip("axicli not on PATH")
    backend = AxiDrawCliBackend(cli_path="axicli")
    status = backend.detect_presence()
    if not status.is_connected:
        pytest.skip("no compatible AxiDraw detected")
    assert status.state.name == "CONNECTED"
