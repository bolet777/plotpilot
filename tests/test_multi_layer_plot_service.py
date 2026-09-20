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
    assert "only-in-layer-b" in fake.plot_file_contents[1]


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
