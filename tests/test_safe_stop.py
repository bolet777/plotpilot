"""Safe stop: cancel plot then raise_pen → walk_home → disable_xy."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plotpilot.models.multi_layer_job import MultiLayerJobState
from plotpilot.models.plot_job import PlotPhase
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


def _wait_plot_started(fake: FakePlotterBackend) -> None:
    wait_until(lambda: len(fake.plot_paths) >= 1)


def _connected_fake(**kwargs: object) -> FakePlotterBackend:
    defaults = {
        "detect_result": PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="ok",
        ),
    }
    defaults.update(kwargs)
    return FakePlotterBackend(**defaults)


def _document_and_layer():
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    return document, layers[0]


def test_stop_active_plot_cancels_subprocess_first(qapp) -> None:
    fake = _connected_fake(plot_block_until_cancel=True)
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document, layer = _document_and_layer()
    service.start_plot_layer(document, layer)
    _wait_plot_started(fake)
    service.request_safe_stop()
    wait_for_safe_stop(service)
    assert fake.cancel_plot_calls >= 1
    plot_exit_idx = fake.manual_sequence.index("plot_exited")
    raise_idx = fake.manual_sequence.index("raise_pen")
    assert plot_exit_idx < raise_idx


def test_raise_pen_after_process_exit(qapp) -> None:
    fake = _connected_fake(plot_block_until_cancel=True)
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document, layer = _document_and_layer()
    service.start_plot_layer(document, layer)
    _wait_plot_started(fake)
    service.request_safe_stop()
    wait_for_safe_stop(service)
    assert fake.manual_sequence.index("plot_exited") < fake.manual_sequence.index("raise_pen")


def test_walk_home_after_raise_pen(qapp) -> None:
    fake = _connected_fake(plot_block_until_cancel=True)
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document, layer = _document_and_layer()
    service.start_plot_layer(document, layer)
    _wait_plot_started(fake)
    service.request_safe_stop()
    wait_for_safe_stop(service)
    assert fake.manual_sequence.index("raise_pen") < fake.manual_sequence.index("walk_home")


def test_disable_xy_after_walk_home(qapp) -> None:
    fake = _connected_fake(plot_block_until_cancel=True)
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document, layer = _document_and_layer()
    service.start_plot_layer(document, layer)
    _wait_plot_started(fake)
    service.request_safe_stop()
    wait_for_safe_stop(service)
    assert fake.manual_sequence.index("walk_home") < fake.manual_sequence.index("disable_xy")


def test_exact_cleanup_command_order(qapp) -> None:
    fake = _connected_fake(plot_block_until_cancel=True)
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document, layer = _document_and_layer()
    service.start_plot_layer(document, layer)
    _wait_plot_started(fake)
    service.request_safe_stop()
    wait_for_safe_stop(service)
    cleanup = fake.manual_sequence[fake.manual_sequence.index("plot_exited") :]
    assert cleanup == ["plot_exited", "raise_pen", "walk_home", "disable_xy"]


def test_multi_layer_stop_uses_same_cleanup(qapp) -> None:
    fake = _connected_fake(plot_block_until_cancel=True)
    plotter = PlotterService(fake)
    plotter._status = fake.detect_result  # noqa: SLF001
    multi = MultiLayerPlotService(plotter)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    multi.start_job(document, layers[:1], settings=PlotSettings())
    _wait_plot_started(fake)
    multi.stop_job()
    wait_for_safe_stop(plotter)
    assert "walk_home" in fake.manual_sequence
    assert "disable_xy" in fake.manual_sequence


def test_stop_while_waiting_for_pen_change_still_cleans_up(qapp) -> None:
    fake = _connected_fake()
    plotter = PlotterService(fake)
    plotter._status = fake.detect_result  # noqa: SLF001
    multi = MultiLayerPlotService(plotter)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    multi.start_job(document, layers, settings=PlotSettings())
    wait_until(lambda: multi.job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert multi.job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE
    fake.manual_sequence.clear()
    multi.stop_job()
    wait_for_safe_stop(plotter)
    assert fake.manual_sequence == ["raise_pen", "walk_home", "disable_xy"]
    assert multi.job.state is MultiLayerJobState.CANCELLED


def test_successful_cleanup_returns_idle(qapp) -> None:
    fake = _connected_fake(plot_block_until_cancel=True)
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document, layer = _document_and_layer()
    service.start_plot_layer(document, layer)
    _wait_plot_started(fake)
    service.request_safe_stop()
    wait_for_safe_stop(service)
    assert service.plot_state.phase is PlotPhase.IDLE
    assert "motors disabled" in service.plot_state.message.lower()


def test_raise_pen_failure_skips_home_and_disable(qapp) -> None:
    fake = _connected_fake(
        pen_up_result=PlotterStatus(
            state=PlotterConnectionState.DISCONNECTED,
            message="pen failed",
        ),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    service.request_safe_stop()
    wait_for_safe_stop(service)
    assert fake.walk_home_calls == 0
    assert fake.disable_xy_calls == 0
    assert "cleanup incomplete" in service.plot_state.message


def test_walk_home_failure_skips_disable_xy(qapp) -> None:
    fake = _connected_fake(
        walk_home_result=PlotterStatus(
            state=PlotterConnectionState.ERROR,
            message="home failed",
        ),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    service.request_safe_stop()
    wait_for_safe_stop(service)
    assert fake.disable_xy_calls == 0
    assert "cleanup incomplete" in service.plot_state.message
    assert "home" not in service.plot_state.message.lower().split("—")[0]


def test_disable_xy_failure_surfaces(qapp) -> None:
    fake = _connected_fake(
        disable_xy_result=PlotterStatus(
            state=PlotterConnectionState.ERROR,
            message="disable failed",
        ),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    service.request_safe_stop()
    result_holder: list[object] = []

    def capture(result: object) -> None:
        result_holder.append(result)

    service.safe_stop_finished.connect(capture)
    wait_for_safe_stop(service)
    assert service.plot_state.phase is PlotPhase.CANCELLED
    assert "disable failed" in service.plot_state.message


def test_repeated_stop_does_not_duplicate_cleanup(qapp) -> None:
    fake = _connected_fake()
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    service.request_safe_stop()
    service.request_safe_stop()
    service.request_safe_stop()
    wait_for_safe_stop(service)
    assert fake.manual_sequence.count("raise_pen") == 1
    assert fake.manual_sequence.count("walk_home") == 1
    assert fake.manual_sequence.count("disable_xy") == 1


def test_no_new_plot_during_cleanup(qapp) -> None:
    fake = _connected_fake(plot_delay_seconds=0.05)
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document, layer = _document_and_layer()
    service.start_plot_layer(document, layer)
    _wait_plot_started(fake)
    service.request_safe_stop()
    err = service.start_plot_layer(document, layer)
    assert err is not None
    wait_for_safe_stop(service)


def test_rapid_stop_clicks_coalesced(qapp) -> None:
    fake = _connected_fake(plot_block_until_cancel=True)
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document, layer = _document_and_layer()
    service.start_plot_layer(document, layer)
    _wait_plot_started(fake)
    for _ in range(5):
        service.request_safe_stop()
    wait_for_safe_stop(service)
    assert fake.disable_xy_calls == 1
