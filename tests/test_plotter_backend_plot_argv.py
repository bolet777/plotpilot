"""AxiDrawCliBackend plot argv (mocked subprocess)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from plotpilot.models.plot_settings import PlotSettings
from plotpilot.plotter.axidraw import AxiDrawCliBackend


def test_plot_svg_uses_build_argv(tmp_path: Path, monkeypatch) -> None:
    svg = tmp_path / "a.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    captured: list[list[str]] = []

    class FakeProc:
        returncode = 0

        def communicate(self):
            return ("ok", "")

        def poll(self):
            return 0

    def fake_popen(argv, **kwargs):
        captured.append(argv)
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    backend = AxiDrawCliBackend(cli_path="axicli")
    monkeypatch.setattr(backend, "_resolve_cli", lambda: "axicli")
    result = backend.plot_svg(
        svg,
        settings=PlotSettings(pen_down_speed=30, acceleration=60),
    )
    assert result.success
    assert captured[0] == [
        "axicli",
        str(svg),
        "-m",
        "plot",
        "-c",
        "1",
        "-s",
        "30",
        "-a",
        "60",
    ]
