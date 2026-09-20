"""AxiDrawCliBackend preview estimate (mocked subprocess)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from plotpilot.models.plot_settings import PlotSettings, build_axicli_preview_argv
from plotpilot.plotter.axidraw import AxiDrawCliBackend

PREVIEW_OUTPUT = """\
Estimated print time: 3.5 Seconds
Length of path to draw: 0.1 m
Pen-up travel distance: 0.2 m
"""


def test_estimate_plot_svg_parses_preview() -> None:
    captured: list[list[str]] = []

    def runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        captured.append(argv)
        return subprocess.CompletedProcess(argv, 0, PREVIEW_OUTPUT, "")

    backend = AxiDrawCliBackend(cli_path="axicli", _runner=runner)
    settings = PlotSettings(pen_down_speed=30, path_reordering=1)
    estimate = backend.estimate_plot_svg(Path("layer.svg"), settings=settings)
    assert estimate is not None
    assert estimate.duration_seconds == 3.5
    expected = build_axicli_preview_argv("axicli", Path("layer.svg"), settings)
    assert captured[0][1:] == expected[1:]


def test_estimate_plot_svg_handles_failure() -> None:
    def runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "", "error")

    backend = AxiDrawCliBackend(cli_path="axicli", _runner=runner)
    assert backend.estimate_plot_svg(Path("layer.svg")) is None
