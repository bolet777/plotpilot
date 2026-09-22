"""MultiLayerPlotService orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plotpilot.models.multi_layer_job import MultiLayerJobState
from plotpilot.models.plot_job import PlotResult
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.multi_layer_plot_service import MultiLayerPlotService
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.svg_loader import load_svg_from_path
from qt_helpers import wait_for_safe_stop, wait_until

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _wait_for_job_state(service: MultiLayerPlotService, state: MultiLayerJobState) -> None:
    wait_until(lambda: service.job.state is state, timeout_ms=5000)
    assert service.job.state is state


def _connected_stack(qapp) -> tuple[MultiLayerPlotService, PlotterService, FakePlotterBackend]:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    )
    plotter = PlotterService(fake)
    plotter._status = fake.detect_result  # noqa: SLF001
    service = MultiLayerPlotService(plotter)
    return service, plotter, fake


def _two_layers():
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    return document, layers


def test_checked_layers_only_in_job_order(qapp) -> None:
    service, _plotter, _fake = _connected_stack(qapp)
    document, layers = _two_layers()
    job_layers = [layers[1], layers[0]]
    service.start_job(document, job_layers, settings=PlotSettings())
    assert [layer.layer_id for layer in service.job.layers] == [
        layers[1].layer_id,
        layers[0].layer_id,
    ]


def test_first_layer_plots_after_start(qapp) -> None:
    service, plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    service.start_job(document, [layers[0]], settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.COMPLETED)
    assert len(fake.plot_paths) == 1


def test_two_layers_pauses_for_pen_change(qapp) -> None:
    service, plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    pen_signals: list[object] = []
    service.pen_change_required.connect(pen_signals.append)
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert len(fake.plot_paths) == 1
    assert fake.pen_up_calls >= 1
    assert len(pen_signals) == 1
    assert len(fake.plot_paths) == 1


def test_continue_starts_next_layer_only(qapp) -> None:
    service, plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    service.continue_after_pen_change()
    _wait_for_job_state(service, MultiLayerJobState.COMPLETED)
    assert len(fake.plot_paths) == 2
    assert "<path " in fake.plot_file_contents[1]


def test_double_continue_does_not_duplicate(qapp) -> None:
    service, plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    service.continue_after_pen_change()
    service.continue_after_pen_change()
    _wait_for_job_state(service, MultiLayerJobState.COMPLETED)
    assert len(fake.plot_paths) == 2


def test_stop_while_waiting(qapp) -> None:
    service, plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    service.stop_job()
    wait_for_safe_stop(plotter)
    assert service.job.state is MultiLayerJobState.CANCELLED
    assert service.job.completed_count == 1
    assert len(fake.plot_paths) == 1
    assert fake.walk_home_calls >= 1
    assert fake.disable_xy_calls >= 1


def test_failure_stops_job(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        plot_result=PlotResult(success=False, message="hardware fault"),
    )
    plotter = PlotterService(fake)
    plotter._status = fake.detect_result  # noqa: SLF001
    service = MultiLayerPlotService(plotter)
    document, layers = _two_layers()
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.ERROR)
    assert len(fake.plot_paths) == 1


def test_settings_snapshot_used(qapp) -> None:
    service, plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    snapshot = PlotSettings(pen_down_speed=42)
    service.start_job(document, [layers[0]], settings=snapshot)
    wait_until(lambda: len(fake.plot_paths) >= 1)
    assert fake.plot_settings_used[-1] == snapshot


def test_multi_layer_each_invocation_gets_reordering_snapshot(qapp) -> None:
    service, plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    snapshot = PlotSettings(path_reordering=1)
    service.start_job(document, layers, settings=snapshot)
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert fake.plot_settings_used == [snapshot]
    service.continue_after_pen_change()
    _wait_for_job_state(service, MultiLayerJobState.COMPLETED)
    assert fake.plot_settings_used == [snapshot, snapshot]


def test_temp_files_cleaned(qapp) -> None:
    service, plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    first = fake.plot_paths[0]
    assert not first.exists()
    service.continue_after_pen_change()
    _wait_for_job_state(service, MultiLayerJobState.COMPLETED)
    second = fake.plot_paths[1]
    assert not second.exists()


def test_pen_change_metadata(qapp) -> None:
    service, plotter, _fake = _connected_stack(qapp)
    document, layers = _two_layers()
    captured: list[object] = []
    service.pen_change_required.connect(captured.append)
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert captured[0].name == layers[1].name


def test_waiting_progress_label_two_layers(qapp) -> None:
    service, _plotter, _fake = _connected_stack(qapp)
    document, layers = _two_layers()
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert service.job.progress_label == "Layer 1 of 2 complete"
    assert service.job.current_layer is not None
    assert service.job.current_layer.name == layers[1].name


def test_three_layer_workflow(qapp) -> None:
    """Third layer uses the same continue/pause chain as two-layer jobs."""
    service, _plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    extra = layers_for_document(load_svg_from_path(FIXTURES / "three_root_groups.svg"))[0]
    job_layers = [layers[0], layers[1], extra]
    service.start_job(document, job_layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert len(fake.plot_paths) == 1
    service.continue_after_pen_change()
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert len(fake.plot_paths) == 2
    service.continue_after_pen_change()
    _wait_for_job_state(service, MultiLayerJobState.COMPLETED)
    assert len(fake.plot_paths) == 3


def test_no_safe_stop_between_layers(qapp) -> None:
    service, _plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert fake.walk_home_calls == 0
    assert fake.disable_xy_calls == 0
    assert "raise_pen" in fake.manual_sequence
    service.continue_after_pen_change()
    _wait_for_job_state(service, MultiLayerJobState.COMPLETED)
    assert fake.walk_home_calls == 0
    assert fake.disable_xy_calls == 0


def test_status_changed_does_not_skip_pen_up(qapp) -> None:
    service, plotter, fake = _connected_stack(qapp)
    document, layers = _two_layers()
    service.start_job(document, layers, settings=PlotSettings())
    wait_until(lambda: fake.plot_paths)
    plotter.status_changed.emit(
        PlotterStatus(state=PlotterConnectionState.CONNECTED, message="presence ping")
    )
    QApplication.processEvents()
    assert service.job.state is MultiLayerJobState.PLOTTING
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)


def test_pen_up_failure_errors_job(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        pen_up_result=PlotterStatus(
            state=PlotterConnectionState.ERROR,
            message="raise_pen failed",
        ),
    )
    plotter = PlotterService(fake)
    plotter._status = fake.detect_result  # noqa: SLF001
    service = MultiLayerPlotService(plotter)
    document, layers = _two_layers()
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.ERROR)
    assert "raise_pen failed" in service.job.message


def test_pen_up_deferred_while_detect_busy_then_recovers(qapp) -> None:
    import threading

    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    detect_started = threading.Event()
    detect_release = threading.Event()

    original_detect = fake.detect

    def slow_detect() -> PlotterStatus:
        detect_started.set()
        detect_release.wait(timeout=5.0)
        return original_detect()

    fake.detect = slow_detect  # type: ignore[method-assign]
    plotter = PlotterService(fake, auto_detect_interval_ms=60_000)
    plotter._status = fake.detect_result  # noqa: SLF001
    service = MultiLayerPlotService(plotter)
    document, layers = _two_layers()
    plotter.refresh()
    wait_until(lambda: detect_started.is_set(), timeout_ms=3000)
    service.start_job(document, layers, settings=PlotSettings())
    wait_until(lambda: fake.plot_paths, timeout_ms=5000)
    wait_until(lambda: service._pen_up_wait, timeout_ms=3000)  # noqa: SLF001
    assert fake.pen_up_calls == 0
    detect_release.set()
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert fake.pen_up_calls >= 1


def test_continue_enabled_after_first_layer(qapp) -> None:
    from plotpilot.ui.main_window import MainWindow

    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    )
    window = MainWindow(plotter_backend=fake)
    window.plotter_service._status = fake.detect_result  # noqa: SLF001
    window._apply_plotter_status(fake.detect_result)
    document, layers = _two_layers()
    window.set_document(document)
    service = window.multi_layer_service
    service.start_job(document, layers, settings=PlotSettings())
    _wait_for_job_state(service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    window._update_plot_controls()
    assert window._multi_continue_button.isEnabled()
    assert window._plot_stop_button.isEnabled()
