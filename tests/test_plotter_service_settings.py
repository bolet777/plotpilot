"""PlotterService passes plot settings snapshot to backend."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_job import PlotPhase
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_model import get_plotter_model_info
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.settings_service import SettingsService
from plotpilot.services.svg_loader import load_svg_from_path
from qt_helpers import (
    wait_for_fake_plot_invocation,
    wait_for_plot_finished,
    wait_for_plot_started,
    wait_for_plot_success,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def test_plot_passes_settings_snapshot(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    settings = SettingsService(organization="PlotPilotTestSvc", application="snap")
    settings.replace(PlotSettings(pen_down_speed=15, model=2))
    service = PlotterService(fake, settings_service=settings)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert service.start_plot_layer(document, layers[0]) is None
    wait_for_plot_success(service)
    assert service.plot_state.phase is PlotPhase.SUCCEEDED
    assert fake.plot_settings_used == [PlotSettings(pen_down_speed=15, model=2)]


def test_plot_passes_path_reordering_snapshot(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    settings = SettingsService(organization="PlotPilotTestSvc", application="reorder")
    settings.replace(PlotSettings(path_reordering=1))
    service = PlotterService(fake, settings_service=settings)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert service.start_plot_layer(document, layers[0]) is None
    wait_for_plot_success(service)
    assert fake.plot_settings_used == [PlotSettings(path_reordering=1)]


def test_changing_settings_during_plot_does_not_alter_snapshot(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    fake.plot_block_until_cancel = True
    settings = SettingsService(organization="PlotPilotTestSvc", application="snap2")
    settings.replace(PlotSettings(path_reordering=1))
    service = PlotterService(fake, settings_service=settings)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    service.start_plot_layer(document, layers[0])
    wait_for_plot_started(service)
    wait_for_fake_plot_invocation(fake)
    settings.replace(PlotSettings(path_reordering=None))
    assert fake.plot_settings_used == [PlotSettings(path_reordering=1)]
    service.cancel_plot()
    wait_for_plot_finished(service)
    fake.plot_block_until_cancel = False
    fake._cancel_event.clear()  # noqa: SLF001
    assert service.start_plot_layer(document, layers[0]) is None
    wait_for_fake_plot_invocation(fake, count=2)
    wait_for_plot_success(service)
    assert fake.plot_settings_used == [
        PlotSettings(path_reordering=1),
        PlotSettings(path_reordering=None),
    ]


def test_plot_uses_clipped_temp_svg_with_reordering_snapshot(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    settings = SettingsService(organization="PlotPilotTestSvc", application="clip")
    settings.replace(PlotSettings(model=1, path_reordering=1))
    service = PlotterService(fake, settings_service=settings)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert service.start_plot_layer(document, layers[0]) is None
    wait_for_plot_success(service)
    model = get_plotter_model_info(1)
    plotted = fake.plot_file_contents[0]
    assert f'width="{model.max_width_mm}mm"' in plotted
    assert f'viewBox="0 0 {model.max_width_mm} {model.max_height_mm}"' in plotted
    assert fake.plot_settings_used == [PlotSettings(model=1, path_reordering=1)]


def test_empty_viewport_intersection_does_not_invoke_backend(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    error = service.start_plot_layer(
        document,
        layers[0],
        artwork_transform=ArtworkTransform(x_mm=10_000.0, y_mm=0.0, scale=1.0),
    )
    assert error is not None
    assert "No artwork intersects" in error
    assert fake.plot_paths == []
