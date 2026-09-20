"""Plot progress model, labels, and PlotterService integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from plotpilot.models.plot_estimate import PlotEstimate, parse_preview_report
from plotpilot.models.plot_job import PlotPhase
from plotpilot.models.plot_progress import (
    RUNNING_PROGRESS_CAP,
    PlotProgressPhase,
    build_running_progress,
    format_plot_duration,
    format_remaining_duration,
    idle_plot_progress,
    running_estimated_fraction,
)
from plotpilot.models.plot_settings import PlotSettings, build_axicli_preview_argv
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plotter_service import PlotterService, shutdown_all_plotter_services
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.plot_progress_labels import (
    progress_fraction_label,
    progress_headline,
    progress_timing_line,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

SAMPLE_PREVIEW = """\
Estimated print time: 120.5 Seconds
Length of path to draw: 1.2 m
Pen-up travel distance: 0.4 m
Total movement distance: 1.6 m
This estimate took 0.010 Seconds
"""


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _wait_for_signal(signal, timeout_ms: int = 5000) -> None:
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    signal.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()
    timer.stop()


def test_idle_plot_progress() -> None:
    progress = idle_plot_progress()
    assert progress.phase is PlotProgressPhase.IDLE
    assert not progress.is_visible


def test_running_estimated_fraction_caps_at_99_percent() -> None:
    assert running_estimated_fraction(50.0, 100.0) == 0.5
    assert running_estimated_fraction(100.0, 100.0) == RUNNING_PROGRESS_CAP
    assert running_estimated_fraction(200.0, 100.0) == RUNNING_PROGRESS_CAP


def test_build_running_progress_remaining() -> None:
    progress = build_running_progress(
        layer_name="Blue",
        elapsed_seconds=30.0,
        estimated_total_seconds=100.0,
        estimate_unavailable=False,
    )
    assert progress.estimated_fraction == 0.3
    assert progress.estimated_remaining_seconds == 70.0
    assert progress.is_estimated is True


def test_format_duration_mm_ss_and_hour() -> None:
    assert format_plot_duration(8) == "00:08"
    assert format_plot_duration(65) == "01:05"
    assert format_plot_duration(272) == "04:32"
    assert format_plot_duration(3661) == "1:01:01"


def test_format_remaining_prefix() -> None:
    assert format_remaining_duration(128, estimated=True) == "~02:08"


def test_parse_preview_report() -> None:
    estimate = parse_preview_report(SAMPLE_PREVIEW)
    assert estimate is not None
    assert estimate.duration_seconds == 120.5
    assert estimate.pen_down_distance_m == 1.2
    assert estimate.pen_up_distance_m == 0.4


def test_parse_preview_report_malformed() -> None:
    assert parse_preview_report("") is None
    assert parse_preview_report("no metrics here") is None


def test_preview_argv_includes_motion_and_g1() -> None:
    settings = PlotSettings(
        pen_down_speed=40,
        pen_up_speed=60,
        acceleration=55,
        model=2,
        path_reordering=1,
    )
    argv = build_axicli_preview_argv("axicli", Path("layer.svg"), settings)
    assert argv[:4] == ["axicli", "layer.svg", "-v", "-T"]
    assert "-s" in argv and "40" in argv
    assert "-S" in argv and "60" in argv
    assert "-a" in argv and "55" in argv
    assert "-L" in argv and "2" in argv
    assert "-G" in argv and "1" in argv


def test_preview_argv_omits_g_without_override() -> None:
    argv = build_axicli_preview_argv("axicli", Path("layer.svg"), PlotSettings())
    assert "-G" not in argv


def test_progress_labels() -> None:
    progress = build_running_progress(
        layer_name="Blue",
        elapsed_seconds=272,
        estimated_total_seconds=400,
        estimate_unavailable=False,
        layer_index=2,
        layer_count=4,
        next_layer_name="Red",
    )
    assert progress_headline(progress) == "Layer 2 of 4 — Blue"
    assert "estimated" in progress_fraction_label(progress)
    assert "04:32" in progress_timing_line(progress)
    assert "~02:08" in progress_timing_line(progress)


def test_plotter_service_progress_with_estimate(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="ok",
        ),
        estimate_result=PlotEstimate(duration_seconds=10.0),
        plot_delay_seconds=0.05,
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    snapshots: list = []
    service.plot_progress_changed.connect(snapshots.append)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert service.start_plot_layer(document, layers[0]) is None
    _wait_for_signal(service.plot_state_changed)
    _wait_for_signal(service.plot_state_changed)
    assert fake.estimate_paths
    assert service.plot_state.phase is PlotPhase.SUCCEEDED
    assert any(
        snap.estimated_total_seconds == 10.0 and snap.estimated_fraction == 1.0
        for snap in snapshots
        if snap.phase is PlotProgressPhase.COMPLETE
    )
    service.shutdown()


def test_estimate_failure_does_not_block_plot(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="ok",
        ),
        estimate_result=None,
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    service.start_plot_layer(document, layers[0])
    _wait_for_signal(service.plot_state_changed)
    _wait_for_signal(service.plot_state_changed)
    assert service.plot_state.phase is PlotPhase.SUCCEEDED
    service.shutdown()


def test_cancelled_plot_not_complete_fraction(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="ok",
        ),
        plot_block_until_cancel=True,
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    service.start_plot_layer(document, layers[0])
    _wait_for_signal(service.plot_state_changed)
    service.request_safe_stop()
    _wait_for_signal(service.safe_stop_finished)
    assert service.plot_progress.phase is PlotProgressPhase.CANCELLED
    assert service.plot_progress.estimated_fraction != 1.0
    service.shutdown()


def test_shutdown_stops_progress_timer(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="ok",
        ),
        plot_block_until_cancel=True,
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    service.start_plot_layer(document, layers[0])
    _wait_for_signal(service.plot_state_changed)
    service.shutdown()
    shutdown_all_plotter_services()
