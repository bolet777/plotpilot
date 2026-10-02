"""Axicli control flags, persistence, manual commands, and pre-plot estimate."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.multi_layer_job import MultiLayerJobState
from plotpilot.models.plot_bounds import BoundsStatus
from plotpilot.models.plot_estimate import PlotEstimate
from plotpilot.models.plot_settings import (
    REORDERING_BASIC,
    REORDERING_FULL,
    REORDERING_STRICT,
    PlotSettings,
    build_axicli_plot_argv,
    build_axicli_preview_argv,
)
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.pre_plot_estimate import PrePlotEstimateReport
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.bounds_service import check_plot_bounds
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.multi_layer_plot_service import MultiLayerPlotService
from plotpilot.services.plot_service import plot_svg_for_layer
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.project_file_service import FORMAT_ID, read_project_file, write_project_file
from plotpilot.services.settings_service import SettingsService, open_settings_store
from plotpilot.services.svg_loader import load_svg_from_path
from qt_helpers import wait_for_plot_started, wait_until

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_A4_PORTRAIT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm"><path d="M0 0"/></svg>'
)


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _unique_switches(argv: list[str]) -> None:
    switches = [item for item in argv if item.startswith("-")]
    assert len(switches) == len(set(switches))


def _connected(fake: FakePlotterBackend | None = None) -> tuple[PlotterService, FakePlotterBackend]:
    backend = fake or FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    service = PlotterService(backend)
    service._status = backend.detect_result  # noqa: SLF001
    return service, backend


def test_argv_modes_are_unique_and_explicit() -> None:
    cases = [
        PlotSettings(),
        PlotSettings(pen_down_speed=40, pen_up_speed=80),
        PlotSettings(acceleration=60),
        PlotSettings(model=2),
        PlotSettings(path_reordering=None),
        PlotSettings(path_reordering=REORDERING_STRICT),
        PlotSettings(path_reordering=REORDERING_BASIC),
        PlotSettings(path_reordering=REORDERING_FULL),
        PlotSettings(pen_pos_up=70, pen_pos_down=25),
        PlotSettings(const_speed=True),
        PlotSettings(
            pen_down_speed=10,
            pen_up_speed=90,
            acceleration=50,
            pen_pos_up=65,
            pen_pos_down=20,
            model=3,
            path_reordering=REORDERING_FULL,
            const_speed=True,
        ),
    ]
    for settings in cases:
        plot_argv = build_axicli_plot_argv("axicli", Path("layer.svg"), settings)
        preview_argv = build_axicli_preview_argv("axicli", Path("layer.svg"), settings)
        _unique_switches(plot_argv)
        _unique_switches(preview_argv)
        assert plot_argv.count("-N") == 1
        assert preview_argv.count("-N") == 1
        assert plot_argv[6:] == preview_argv[4:]

    combined = build_axicli_plot_argv(
        "axicli",
        Path("layer.svg"),
        PlotSettings(
            pen_down_speed=10,
            pen_up_speed=90,
            acceleration=50,
            pen_pos_up=65,
            pen_pos_down=20,
            model=3,
            path_reordering=REORDERING_FULL,
            const_speed=True,
        ),
    )
    assert combined == [
        "axicli",
        "layer.svg",
        "-m",
        "plot",
        "-c",
        "1",
        "-s",
        "10",
        "-S",
        "90",
        "-a",
        "50",
        "-u",
        "65",
        "-d",
        "20",
        "-L",
        "3",
        "-G",
        "2",
        "-N",
        "-C",
    ]


def test_const_speed_off_omits_flag() -> None:
    argv = build_axicli_plot_argv("axicli", Path("layer.svg"), PlotSettings(const_speed=False))
    assert "-C" not in argv


@pytest.mark.parametrize(
    ("ordering", "flag"),
    [
        (None, None),
        (REORDERING_STRICT, "4"),
        (REORDERING_BASIC, "1"),
        (REORDERING_FULL, "2"),
    ],
)
def test_path_ordering_flag(ordering: int | None, flag: str | None) -> None:
    argv = build_axicli_plot_argv(
        "axicli",
        Path("layer.svg"),
        PlotSettings(path_reordering=ordering),
    )
    if flag is None:
        assert "-G" not in argv
    else:
        assert argv[argv.index("-G") + 1] == flag


def test_orientation_policy_matches_preview_assumption() -> None:
    argv = build_axicli_plot_argv("axicli", Path("page.svg"), PlotSettings(model=1))
    preview = build_axicli_preview_argv("axicli", Path("page.svg"), PlotSettings(model=1))
    assert "-N" in argv and "-N" in preview
    portrait = check_plot_bounds(_A4_PORTRAIT, PlotSettings(model=1))
    assert portrait.status is BoundsStatus.OUT_OF_BOUNDS
    assert portrait.document_width_mm == 210
    assert portrait.document_height_mm == 297
    assert portrait.would_fit_if_rotated


def test_new_settings_persist(qapp) -> None:
    org = f"PlotPilotTest-{uuid.uuid4().hex}"
    app = f"PlotPilotTest-{uuid.uuid4().hex}"
    service = SettingsService(organization=org, application=app)
    service.replace(
        PlotSettings(
            pen_pos_up=72,
            pen_pos_down=18,
            const_speed=True,
            path_reordering=REORDERING_FULL,
        )
    )
    reloaded = SettingsService(organization=org, application=app)
    assert reloaded.plot_settings.pen_pos_up == 72
    assert reloaded.plot_settings.pen_pos_down == 18
    assert reloaded.plot_settings.const_speed is True
    assert reloaded.plot_settings.path_reordering == REORDERING_FULL
    open_settings_store(org, app).clear()


def test_driver_default_path_order_persists(qapp) -> None:
    org = f"PlotPilotTest-{uuid.uuid4().hex}"
    app = f"PlotPilotTest-{uuid.uuid4().hex}"
    service = SettingsService(organization=org, application=app)
    service.replace(PlotSettings(path_reordering=None))
    store = open_settings_store(org, app)
    assert store.value("plot/path_reordering") == "driver"
    reloaded = SettingsService(organization=org, application=app)
    assert reloaded.plot_settings.path_reordering is None
    open_settings_store(org, app).clear()


def test_missing_qsettings_path_order_is_strict(qapp) -> None:
    org = f"PlotPilotTest-{uuid.uuid4().hex}"
    app = f"PlotPilotTest-{uuid.uuid4().hex}"
    loaded = SettingsService(organization=org, application=app)
    assert loaded.plot_settings.path_reordering == REORDERING_STRICT
    assert loaded.plot_settings.const_speed is False
    assert loaded.plot_settings.pen_pos_up is None
    open_settings_store(org, app).clear()


def test_legacy_project_omits_new_keys(tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    project = tmp_path / "old.plotpilot"
    project.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(svg)},
                "plot_settings": {
                    "pen_down_speed": 30,
                    "pen_up_speed": None,
                    "acceleration": None,
                    "model": 1,
                    "path_reordering": None,
                },
            }
        ),
        encoding="utf-8",
    )
    loaded = read_project_file(project)
    assert loaded.plot_settings == PlotSettings(
        pen_down_speed=30,
        model=1,
        path_reordering=None,
        pen_pos_up=None,
        pen_pos_down=None,
        const_speed=False,
    )


def test_project_round_trip_new_fields(tmp_path: Path) -> None:
    from plotpilot.models.project_session import ProjectSession
    from plotpilot.services.preview_work_area import FallbackWorkArea

    svg = FIXTURES / "simple.svg"
    session = ProjectSession(
        svg_path=svg.resolve(),
        checked_layer_ids=(),
        artwork_transform=ArtworkTransform.identity(),
        plot_settings=PlotSettings(
            pen_pos_up=55,
            pen_pos_down=22,
            const_speed=True,
            path_reordering=REORDERING_BASIC,
        ),
        fallback_work_area=FallbackWorkArea.A4,
    )
    project = tmp_path / "new.plotpilot"
    write_project_file(project, session)
    assert read_project_file(project).plot_settings == session.plot_settings


def test_plot_snapshot_includes_new_fields(qapp) -> None:
    service, fake = _connected()
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layer = layers_for_document(document)[0]
    snapshot = PlotSettings(pen_pos_up=61, pen_pos_down=29, const_speed=True, model=1)
    assert service.start_plot_layer(document, layer, plot_settings=snapshot) is None
    wait_until(lambda: fake.plot_settings_used == [snapshot])


def test_multi_layer_snapshot_includes_new_fields(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    plotter = PlotterService(fake)
    plotter._status = fake.detect_result  # noqa: SLF001
    service = MultiLayerPlotService(plotter)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    snapshot = PlotSettings(pen_pos_down=15, const_speed=True, path_reordering=REORDERING_FULL)
    service.start_job(document, layers, settings=snapshot)
    wait_until(lambda: service.job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert fake.plot_settings_used == [snapshot]
    service.continue_after_pen_change()
    wait_until(lambda: service.job.state is MultiLayerJobState.COMPLETED, timeout_ms=5000)
    assert fake.plot_settings_used == [snapshot, snapshot]


def test_home_and_motors_off_are_single_manual_commands(qapp) -> None:
    service, fake = _connected()
    assert service.home() is None
    wait_until(lambda: fake.walk_home_calls == 1 and not service.manual_command_active)
    assert fake.manual_sequence == ["walk_home"]
    assert service.motors_off() is None
    wait_until(lambda: fake.disable_xy_calls == 1 and not service.manual_command_active)
    assert fake.manual_sequence == ["walk_home", "disable_xy"]
    assert "lower_pen" not in fake.manual_sequence


def test_home_and_motors_off_refused_while_plot_active(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        plot_block_until_cancel=True,
    )
    service, _backend = _connected(fake)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layer = layers_for_document(document)[0]
    assert service.start_plot_layer(document, layer) is None
    wait_for_plot_started(service)
    assert service.home() == "Cannot run this command while a plot is active."
    assert service.motors_off() == "Cannot run this command while a plot is active."
    assert fake.walk_home_calls == 0
    assert fake.disable_xy_calls == 0
    service.cancel_plot()


def test_estimate_uses_prepared_svg_not_source(qapp) -> None:
    estimate = PlotEstimate(
        duration_seconds=12.5,
        pen_down_distance_m=1.25,
        pen_up_distance_m=0.4,
    )
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        estimate_result=estimate,
    )
    service, _backend = _connected(fake)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layer = layers_for_document(document)[0]
    settings = PlotSettings(model=1, path_reordering=REORDERING_BASIC)
    prepared = prepare_layer_plot_svg(
        plot_svg_for_layer(document, layer),
        plot_settings=settings,
        transform=ArtworkTransform.identity(),
    )
    reports: list[PrePlotEstimateReport] = []
    service.pre_plot_estimate_changed.connect(reports.append)
    assert (
        service.request_pre_plot_estimate(
            document,
            [layer],
            plot_settings=settings,
        )
        is None
    )
    wait_until(lambda: any(report.state == "ready" for report in reports))
    assert fake.estimate_file_contents == [prepared.svg_text]
    assert prepared.svg_text != document.raw_text
    assert fake.estimate_settings_used == [settings]
    ready = reports[-1]
    assert ready.drawing_seconds == 12.5
    assert ready.pen_down_distance_m == 1.25
    assert ready.pen_up_distance_m == 0.4
    assert "Pen down: 1.250 m" in ready.summary
    assert "Pen up: 0.400 m" in ready.summary
    assert "Pen-change" not in ready.summary


def test_multi_layer_estimate_totals_drawing_time_only(qapp) -> None:
    estimate = PlotEstimate(
        duration_seconds=10.0,
        pen_down_distance_m=1.0,
        pen_up_distance_m=0.25,
    )
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        estimate_result=estimate,
    )
    service, _backend = _connected(fake)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    reports: list[PrePlotEstimateReport] = []
    service.pre_plot_estimate_changed.connect(reports.append)
    error = service.request_pre_plot_estimate(
        document,
        layers,
        plot_settings=PlotSettings(model=1),
    )
    assert error is None
    wait_until(lambda: any(report.state == "ready" for report in reports))
    ready = reports[-1]
    assert ready.drawing_seconds == 20.0
    assert ready.pen_down_distance_m == 2.0
    assert ready.pen_up_distance_m == 0.5
    assert "Total drawing" in ready.summary
    assert "Pen-change pauses are not included." in ready.summary
    assert len(fake.estimate_file_contents) == 2


def test_estimate_refused_while_plot_active(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        plot_block_until_cancel=True,
    )
    service, _backend = _connected(fake)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert service.start_plot_layer(document, layers[0]) is None
    wait_for_plot_started(service)
    error = service.request_pre_plot_estimate(document, layers)
    assert error == "Cannot estimate while a plot is active."
    assert fake.estimate_paths == []
    service.cancel_plot()
