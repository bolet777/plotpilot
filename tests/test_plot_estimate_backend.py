"""AxiDrawCliBackend preview estimate (mocked subprocess)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from plotpilot.models.plot_estimate import parse_preview_report
from plotpilot.models.plot_settings import PlotSettings, build_axicli_preview_argv
from plotpilot.models.pre_plot_estimate import build_pre_plot_estimate_report
from plotpilot.plotter.axidraw import AxiDrawCliBackend

# Captured from axicli 3.9.6 `axicli file.svg -v -T -G 4 -N` (stderr, empty stdout).
REAL_STDERR_UNDER_10S = """\
Estimated print time: 2.052 Seconds
Length of path to draw: 0.053 m
Pen-up travel distance: 0.037 m
Total movement distance: 0.090 m
This estimate took 0.000 Seconds
"""
REAL_STDERR_OVER_MINUTE = """\
Estimated print time: 3:00 (Minutes, seconds)
Length of path to draw: 7.840 m
Pen-up travel distance: 0.317 m
Total movement distance: 8.157 m
This estimate took 0.002 Seconds
"""
REAL_STDERR_TENS_OF_SECONDS = """\
Estimated print time: 36 Seconds
Length of path to draw: 1.568 m
Pen-up travel distance: 0.150 m
Total movement distance: 1.718 m
This estimate took 0.001 Seconds
"""
# Same formatter axicli uses (plotink.text_utils.format_hms) for >= 1 hour.
HOUR_TIME_REPORT = """\
Estimated print time: 1:02:03 (Hours, minutes, seconds)
Length of path to draw: 12.000 m
Pen-up travel distance: 1.500 m
"""

PREVIEW_OUTPUT = """\
Estimated print time: 3.5 Seconds
Length of path to draw: 0.1 m
Pen-up travel distance: 0.2 m
"""


def test_injected_runner_does_not_need_axicli_installed(monkeypatch) -> None:
    monkeypatch.setattr("plotpilot.plotter.axidraw.resolve_cli_executable", lambda _name: None)

    def runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, PREVIEW_OUTPUT, "")

    backend = AxiDrawCliBackend(cli_path="axicli", _runner=runner)
    estimate = backend.estimate_plot_svg(Path("layer.svg"))
    assert estimate is not None
    assert estimate.duration_seconds == 3.5


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
        return subprocess.CompletedProcess(argv, 2, "", "usage: axicli svg_in [OPTIONS]\n")

    backend = AxiDrawCliBackend(cli_path="axicli", _runner=runner)
    assert backend.estimate_plot_svg(Path("layer.svg")) is None
    outcome = backend.estimate_preview(Path("layer.svg"))
    assert outcome.estimate is None
    assert outcome.failure == "axicli returned exit code 2"
    assert "usage:" not in (outcome.failure or "")


def test_estimate_reads_realistic_report_from_stderr() -> None:
    def runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, "", REAL_STDERR_OVER_MINUTE)

    backend = AxiDrawCliBackend(cli_path="axicli", _runner=runner)
    estimate = backend.estimate_plot_svg(Path("layer.svg"))
    assert estimate is not None
    assert estimate.duration_seconds == 180
    assert estimate.pen_down_distance_m == 7.840
    assert estimate.pen_up_distance_m == 0.317


def test_parse_realistic_axicli_time_formats() -> None:
    under = parse_preview_report(REAL_STDERR_UNDER_10S)
    assert under is not None
    assert under.duration_seconds == 2.052
    assert under.pen_down_distance_m == 0.053
    assert under.pen_up_distance_m == 0.037

    tens = parse_preview_report(REAL_STDERR_TENS_OF_SECONDS)
    assert tens is not None
    assert tens.duration_seconds == 36

    hours = parse_preview_report(HOUR_TIME_REPORT)
    assert hours is not None
    assert hours.duration_seconds == 3723

    stdout_only = parse_preview_report(PREVIEW_OUTPUT)
    assert stdout_only is not None
    assert stdout_only.duration_seconds == 3.5


def test_parse_missing_pen_up_field() -> None:
    text = "Estimated print time: 4.5 Seconds\nLength of path to draw: 0.250 m\n"
    estimate = parse_preview_report(text)
    assert estimate is not None
    assert estimate.duration_seconds == 4.5
    assert estimate.pen_down_distance_m == 0.250
    assert estimate.pen_up_distance_m is None


def test_unavailable_summary_keeps_exit_code_and_hides_stderr() -> None:
    report = build_pre_plot_estimate_report(
        [("Layer A", None, "axicli returned exit code 2")],
    )
    assert report.summary == "Estimate unavailable — axicli returned exit code 2"
    assert "Traceback" not in report.summary
