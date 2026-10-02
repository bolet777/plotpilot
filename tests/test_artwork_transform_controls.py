"""Modern artwork transform slider controls."""

from __future__ import annotations

import pytest
from PySide6.QtTest import QSignalSpy

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.print_margins import PrintMargins, printable_area_for
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    WorkAreaOrientation,
    resolve_preview_work_area,
)
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.artwork_transform_controls import ArtworkTransformControls
from plotpilot.ui.main_window import MainWindow
from plotpilot.ui.transform_slider_mapping import (
    ArtworkBoundsMm,
    axis_translation_limits,
    mm_to_position_slider,
    position_slider_to_mm,
    scale_slider_to_percent,
)

FIXTURES = __import__("pathlib").Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def controls(qapp) -> ArtworkTransformControls:
    widget = ArtworkTransformControls()
    widget.set_artwork_bounds(ArtworkBoundsMm(0.0, 100.0, 0.0, 80.0))
    widget.set_work_area_dimensions(300.0, 217.9)
    widget.show()
    return widget


def _set_axis_slider(controls: ArtworkTransformControls, axis: str, mm: float) -> None:
    if axis == "X":
        slider = controls._x_slider
        limits = controls.x_slider_limits()
    else:
        slider = controls._y_slider
        limits = controls.y_slider_limits()
    slider.setValue(mm_to_position_slider(mm, limits[0], limits[1]))


def test_x_slider_updates_x_preserves_y_and_scale(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform(x_mm=0.0, y_mm=12.0, scale=1.14))
    spy = QSignalSpy(controls.transform_changed)
    _set_axis_slider(controls, "X", 37.5)
    assert spy.count() == 1
    emitted = spy.at(0)[0]
    assert emitted.x_mm == pytest.approx(37.5, abs=0.05)
    assert emitted.y_mm == pytest.approx(12.0)
    assert emitted.scale == pytest.approx(1.14)
    assert controls._x_spin.value() == pytest.approx(37.5, abs=0.05)


def test_y_slider_updates_y_preserves_x_and_scale(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform(x_mm=-4.0, y_mm=0.0, scale=0.5))
    spy = QSignalSpy(controls.transform_changed)
    _set_axis_slider(controls, "Y", -10.0)
    emitted = spy.at(0)[0]
    assert emitted.y_mm == pytest.approx(-10.0, abs=0.05)
    assert emitted.x_mm == pytest.approx(-4.0)
    assert emitted.scale == pytest.approx(0.5)


def test_scale_slider_and_spin_stay_synchronized(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform.identity())
    spy = QSignalSpy(controls.transform_changed)
    target = 114
    controls._scale_spin.setValue(target)
    assert controls._scale_spin.value() == pytest.approx(target)
    slider_percent = scale_slider_to_percent(controls._scale_slider.value())
    assert slider_percent == pytest.approx(target, abs=0.15)
    assert spy.at(spy.count() - 1)[0].scale == pytest.approx(1.14)


def test_scale_presets_apply_and_highlight_exact_match(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform(scale=1.0))
    assert controls._preset_buttons[100.0].isChecked()
    controls._preset_buttons[150.0].click()
    assert controls._scale_spin.value() == pytest.approx(150.0)
    assert controls._preset_buttons[150.0].isChecked()
    assert not controls._preset_buttons[100.0].isChecked()
    controls.set_transform(ArtworkTransform(scale=1.14))
    assert not any(button.isChecked() for button in controls._preset_buttons.values())


def test_reset_axes_and_all(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform(x_mm=5.0, y_mm=-3.0, scale=1.5))
    spy = QSignalSpy(controls.transform_changed)
    controls._reset_x.click()
    last = spy.at(spy.count() - 1)[0]
    assert last.x_mm == pytest.approx(0.0)
    assert last.y_mm == pytest.approx(-3.0)
    assert last.scale == pytest.approx(1.5)
    controls._reset_y.click()
    assert spy.at(spy.count() - 1)[0].y_mm == pytest.approx(0.0)
    controls._reset_all.click()
    assert spy.at(spy.count() - 1)[0] == ArtworkTransform.identity()


def test_work_area_change_updates_slider_range_preserves_transform(
    controls: ArtworkTransformControls,
) -> None:
    controls.set_transform(ArtworkTransform(x_mm=40.0, y_mm=-5.0, scale=1.25))
    spy = QSignalSpy(controls.transform_changed)
    controls.set_work_area_dimensions(297.0, 210.0)
    assert spy.count() == 0
    assert controls._x_spin.value() == pytest.approx(40.0)
    assert controls._y_spin.value() == pytest.approx(-5.0)
    assert controls._scale == pytest.approx(1.25)
    area = printable_area_for(297.0, 210.0, controls.print_margins())
    assert controls.x_translation_limits() == pytest.approx(
        axis_translation_limits(
            artwork_min_mm=0.0,
            artwork_max_mm=100.0,
            scale=1.25,
            printable_min_mm=area.x_mm,
            printable_max_mm=area.x_max_mm,
        ),
    )
    shown_min, shown_max = controls.x_slider_limits()
    assert position_slider_to_mm(controls._x_slider.value(), shown_min, shown_max) == pytest.approx(
        40.0,
        abs=0.05,
    )


def test_preview_drag_updates_controls_without_feedback_loop(qapp) -> None:
    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    window._set_artwork_transform(ArtworkTransform(x_mm=1.0, y_mm=2.0, scale=1.0))
    set_calls: list[ArtworkTransform] = []
    original_set = window._set_artwork_transform

    def counting(transform: ArtworkTransform, **kwargs: object) -> None:
        set_calls.append(transform)
        original_set(transform, **kwargs)

    window._set_artwork_transform = counting  # type: ignore[method-assign]
    dragged = ArtworkTransform(x_mm=9.0, y_mm=-4.0, scale=1.0)
    window._preview.set_artwork_transform(dragged)
    window._on_preview_artwork_dragged(dragged)
    assert set_calls == []
    assert window._artwork_controls._x_spin.value() == pytest.approx(9.0)
    assert window._artwork_controls._y_spin.value() == pytest.approx(-4.0)
    window.close()


def test_controls_to_preview_single_authoritative_update(qapp) -> None:
    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    window._artwork_controls._x_spin.setValue(6.0)
    assert window._preview.artwork_transform.x_mm == pytest.approx(6.0)
    window.close()


def test_slider_callback_does_not_flatten_on_caller(
    qapp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plotpilot.services import layer_geometry

    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    flatten_calls: list[str] = []
    original = layer_geometry.flatten_document_geometry

    def wrapped(svg_text: str):
        flatten_calls.append("flatten")
        return original(svg_text)

    monkeypatch.setattr(layer_geometry, "flatten_document_geometry", wrapped)
    window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    flatten_calls.clear()
    slider = window._artwork_controls._x_slider
    slider.setValue(0 if slider.value() != 0 else slider.maximum())
    assert flatten_calls == []
    window.close()


@pytest.mark.parametrize(
    ("model", "fallback", "orientation"),
    [
        (1, FallbackWorkArea.A4, WorkAreaOrientation.PORTRAIT),
        (None, FallbackWorkArea.A4, WorkAreaOrientation.PORTRAIT),
        (None, FallbackWorkArea.A4, WorkAreaOrientation.LANDSCAPE),
    ],
)
def test_main_window_slider_ranges_from_work_area(
    qapp,
    model: int | None,
    fallback: FallbackWorkArea,
    orientation: WorkAreaOrientation,
) -> None:
    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    window._settings_service.replace(PlotSettings(model=model))
    window._settings_service.set_preview_fallback_work_area(fallback)
    window._settings_service.set_preview_fallback_work_area_orientation(orientation)
    window._refresh_artwork_transform_panel()
    area = resolve_preview_work_area(
        PlotSettings(model=model),
        fallback=fallback,
        fallback_orientation=orientation,
    )
    assert area is not None
    printable = printable_area_for(
        area.width_mm,
        area.height_mm,
        window._settings_service.print_margins,
    )
    assert window._artwork_controls.x_translation_limits() == pytest.approx(
        axis_translation_limits(
            artwork_min_mm=0.0,
            artwork_max_mm=0.0,
            scale=1.0,
            printable_min_mm=printable.x_mm,
            printable_max_mm=printable.x_max_mm,
        ),
    )
    assert window._artwork_controls.y_translation_limits() == pytest.approx(
        axis_translation_limits(
            artwork_min_mm=0.0,
            artwork_max_mm=0.0,
            scale=1.0,
            printable_min_mm=printable.y_mm,
            printable_max_mm=printable.y_max_mm,
        ),
    )
    window.close()


def test_scale_change_recomputes_xy_ranges_without_moving_artwork(
    controls: ArtworkTransformControls,
) -> None:
    controls.set_transform(ArtworkTransform(x_mm=12.0, y_mm=-4.0, scale=1.0))
    area = printable_area_for(300.0, 217.9, controls.print_margins())
    before_x = controls.x_translation_limits()
    spy = QSignalSpy(controls.transform_changed)
    controls._scale_spin.setValue(200)
    emitted = spy.at(spy.count() - 1)[0]
    assert emitted.x_mm == pytest.approx(12.0)
    assert emitted.y_mm == pytest.approx(-4.0)
    assert emitted.scale == pytest.approx(2.0)
    assert controls._x_spin.value() == pytest.approx(12.0)
    assert controls._y_spin.value() == pytest.approx(-4.0)
    expected_x = axis_translation_limits(
        artwork_min_mm=0.0,
        artwork_max_mm=100.0,
        scale=2.0,
        printable_min_mm=area.x_mm,
        printable_max_mm=area.x_max_mm,
    )
    expected_y = axis_translation_limits(
        artwork_min_mm=0.0,
        artwork_max_mm=80.0,
        scale=2.0,
        printable_min_mm=area.y_mm,
        printable_max_mm=area.y_max_mm,
    )
    assert controls.x_translation_limits() == pytest.approx(expected_x)
    assert controls.y_translation_limits() == pytest.approx(expected_y)
    assert controls.x_translation_limits() != pytest.approx(before_x)


def test_recomputing_ranges_does_not_change_artwork_transform(
    controls: ArtworkTransformControls,
) -> None:
    controls.set_transform(ArtworkTransform(x_mm=8.0, y_mm=3.0, scale=1.5))
    spy = QSignalSpy(controls.transform_changed)
    controls.set_artwork_bounds(ArtworkBoundsMm(20.0, 80.0, 15.0, 55.0))
    controls.set_work_area_dimensions(420.0, 297.0)
    controls.set_print_margins(PrintMargins(horizontal_mm=18.0, vertical_mm=14.0))
    assert spy.count() == 0
    assert controls._x_spin.value() == pytest.approx(8.0)
    assert controls._y_spin.value() == pytest.approx(3.0)
    assert controls._scale == pytest.approx(1.5)
    area = printable_area_for(420.0, 297.0, PrintMargins(18.0, 14.0))
    assert controls.x_translation_limits() == pytest.approx(
        axis_translation_limits(
            artwork_min_mm=20.0,
            artwork_max_mm=80.0,
            scale=1.5,
            printable_min_mm=area.x_mm,
            printable_max_mm=area.x_max_mm,
        ),
    )
    assert controls.y_translation_limits() == pytest.approx(
        axis_translation_limits(
            artwork_min_mm=15.0,
            artwork_max_mm=55.0,
            scale=1.5,
            printable_min_mm=area.y_mm,
            printable_max_mm=area.y_max_mm,
        ),
    )


def test_slider_extremes_move_scaled_artwork_across_printable_area(
    controls: ArtworkTransformControls,
) -> None:
    controls.set_artwork_bounds(ArtworkBoundsMm(0.0, 180.0, 0.0, 160.0))
    controls.set_work_area_dimensions(210.0, 297.0)
    controls.set_print_margins(PrintMargins(horizontal_mm=10.0, vertical_mm=10.0))
    controls.set_transform(ArtworkTransform(scale=2.0))
    area = printable_area_for(210.0, 297.0, PrintMargins(10.0, 10.0))

    controls._x_slider.setValue(0)
    x_at_min = controls._x_spin.value()
    controls._x_slider.setValue(controls._x_slider.maximum())
    x_at_max = controls._x_spin.value()
    assert 360.0 + x_at_min == pytest.approx(area.x_mm, abs=0.05)
    assert 0.0 + x_at_max == pytest.approx(area.x_max_mm, abs=0.05)

    controls._y_slider.setValue(0)
    y_at_min = controls._y_spin.value()
    controls._y_slider.setValue(controls._y_slider.maximum())
    y_at_max = controls._y_spin.value()
    assert 320.0 + y_at_min == pytest.approx(area.y_mm, abs=0.05)
    assert 0.0 + y_at_max == pytest.approx(area.y_max_mm, abs=0.05)


def test_out_of_range_translation_stays_representable(
    controls: ArtworkTransformControls,
) -> None:
    controls.set_transform(ArtworkTransform(x_mm=1500.0, y_mm=-1800.0, scale=1.5))
    spy = QSignalSpy(controls.transform_changed)
    controls.set_artwork_bounds(ArtworkBoundsMm(10.0, 40.0, 5.0, 25.0))
    controls.set_work_area_dimensions(210.0, 297.0)
    assert spy.count() == 0
    assert controls._x_spin.value() == pytest.approx(1500.0)
    assert controls._y_spin.value() == pytest.approx(-1800.0)
    assert controls._scale == pytest.approx(1.5)
    x_min, x_max = controls.x_slider_limits()
    y_min, y_max = controls.y_slider_limits()
    assert position_slider_to_mm(controls._x_slider.value(), x_min, x_max) == pytest.approx(
        1500.0,
        abs=0.05,
    )
    assert position_slider_to_mm(controls._y_slider.value(), y_min, y_max) == pytest.approx(
        -1800.0,
        abs=0.05,
    )
    calc_min, calc_max = controls.x_translation_limits()
    assert calc_max < 1500.0
    assert position_slider_to_mm(0, x_min, x_max) <= calc_min + 1e-6
    assert position_slider_to_mm(controls._x_slider.maximum(), x_min, x_max) >= calc_max - 1e-6


def test_numeric_position_edit_accepts_values_outside_slider_travel(
    controls: ArtworkTransformControls,
) -> None:
    controls.set_transform(ArtworkTransform.identity())
    spy = QSignalSpy(controls.transform_changed)
    controls._x_spin.setValue(1234.5)
    controls._y_spin.setValue(-999.0)
    emitted = spy.at(spy.count() - 1)[0]
    assert emitted.x_mm == pytest.approx(1234.5)
    assert emitted.y_mm == pytest.approx(-999.0)
    assert controls._x_spin.value() == pytest.approx(1234.5)
    assert controls._y_spin.value() == pytest.approx(-999.0)


def _apply_prepared_preview(window: MainWindow, qapp: object) -> None:
    from PySide6.QtCore import QThreadPool

    window._preview_prep_timer.stop()
    assert QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()
    window._refresh_prepared_preview()
    assert QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


def _expected_limits(
    window: MainWindow,
    *,
    artwork_min_mm: float,
    artwork_max_mm: float,
    scale: float,
    axis: str,
) -> tuple[float, float]:
    work = resolve_preview_work_area(
        window._settings_service.plot_settings,
        fallback=window._settings_service.preview_fallback_work_area,
        fallback_orientation=window._settings_service.preview_fallback_work_area_orientation,
    )
    assert work is not None
    printable = printable_area_for(
        work.width_mm,
        work.height_mm,
        window._artwork_controls.print_margins(),
    )
    if axis == "X":
        return axis_translation_limits(
            artwork_min_mm=artwork_min_mm,
            artwork_max_mm=artwork_max_mm,
            scale=scale,
            printable_min_mm=printable.x_mm,
            printable_max_mm=printable.x_max_mm,
        )
    return axis_translation_limits(
        artwork_min_mm=artwork_min_mm,
        artwork_max_mm=artwork_max_mm,
        scale=scale,
        printable_min_mm=printable.y_mm,
        printable_max_mm=printable.y_max_mm,
    )


def test_selected_layer_bounds_and_page_setup_recompute_ranges(qapp) -> None:
    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    window._settings_service.begin_project_session(
        PlotSettings(),
        FallbackWorkArea.A4,
        WorkAreaOrientation.PORTRAIT,
        window._artwork_controls.print_margins(),
    )
    window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    _apply_prepared_preview(window, qapp)

    # Stroke bounds are 10..90 mm, not the 0..100 mm page.
    assert window._artwork_controls.x_translation_limits() == pytest.approx(
        _expected_limits(
            window,
            artwork_min_mm=10.0,
            artwork_max_mm=90.0,
            scale=1.0,
            axis="X",
        ),
    )
    assert window._artwork_controls.x_translation_limits() != pytest.approx(
        _expected_limits(
            window,
            artwork_min_mm=0.0,
            artwork_max_mm=100.0,
            scale=1.0,
            axis="X",
        ),
    )

    window._artwork_controls._scale_spin.setValue(200)
    assert window._preview.artwork_transform == ArtworkTransform(scale=2.0)
    assert window._artwork_controls.x_translation_limits() == pytest.approx(
        _expected_limits(
            window,
            artwork_min_mm=10.0,
            artwork_max_mm=90.0,
            scale=2.0,
            axis="X",
        ),
    )
    assert window._artwork_controls.y_translation_limits() == pytest.approx(
        _expected_limits(
            window,
            artwork_min_mm=10.0,
            artwork_max_mm=90.0,
            scale=2.0,
            axis="Y",
        ),
    )

    window._settings_service.replace(PlotSettings(model=1))
    window._refresh_artwork_transform_panel()
    assert window._preview.artwork_transform == ArtworkTransform(scale=2.0)
    assert window._artwork_controls.x_translation_limits() == pytest.approx(
        _expected_limits(
            window,
            artwork_min_mm=10.0,
            artwork_max_mm=90.0,
            scale=2.0,
            axis="X",
        ),
    )

    window._settings_service.replace(PlotSettings())
    window._settings_service.set_preview_fallback_work_area(FallbackWorkArea.A3)
    window._settings_service.set_preview_fallback_work_area_orientation(
        WorkAreaOrientation.LANDSCAPE,
    )
    window._refresh_artwork_transform_panel()
    assert window._preview.artwork_transform == ArtworkTransform(scale=2.0)
    landscape_x = window._artwork_controls.x_translation_limits()
    assert landscape_x == pytest.approx(
        _expected_limits(
            window,
            artwork_min_mm=10.0,
            artwork_max_mm=90.0,
            scale=2.0,
            axis="X",
        ),
    )

    window._artwork_controls._margin_horizontal.setValue(22.0)
    window._artwork_controls._margin_vertical.setValue(8.0)
    assert window._preview.artwork_transform == ArtworkTransform(scale=2.0)
    assert window._artwork_controls.x_translation_limits() == pytest.approx(
        _expected_limits(
            window,
            artwork_min_mm=10.0,
            artwork_max_mm=90.0,
            scale=2.0,
            axis="X",
        ),
    )
    assert window._artwork_controls.x_translation_limits() != pytest.approx(landscape_x)
    window.close()


def test_programmatic_transform_updates_controls(qapp) -> None:
    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    window._set_artwork_transform(ArtworkTransform(x_mm=5.0, y_mm=-2.0, scale=2.0))
    assert window._artwork_controls._x_spin.value() == pytest.approx(5.0)
    assert window._artwork_controls._scale_spin.value() == pytest.approx(200.0)
    window.close()
