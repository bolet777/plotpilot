"""Modern artwork transform slider controls."""

from __future__ import annotations

import pytest
from PySide6.QtTest import QSignalSpy

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
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
    mm_to_position_slider,
    position_slider_to_mm,
    scale_slider_to_percent,
)

FIXTURES = __import__("pathlib").Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def controls(qapp) -> ArtworkTransformControls:
    widget = ArtworkTransformControls()
    widget.set_work_area_dimensions(300.0, 217.9)
    widget.show()
    return widget


def test_x_slider_updates_x_preserves_y_and_scale(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform(x_mm=0.0, y_mm=12.0, scale=1.14))
    spy = QSignalSpy(controls.transform_changed)
    controls._x_slider.setValue(mm_to_position_slider(37.5, 300.0))
    assert spy.count() == 1
    emitted = spy.at(0)[0]
    assert emitted.x_mm == pytest.approx(37.5, abs=0.05)
    assert emitted.y_mm == pytest.approx(12.0)
    assert emitted.scale == pytest.approx(1.14)
    assert controls._x_spin.value() == pytest.approx(37.5, abs=0.05)


def test_y_slider_updates_y_preserves_x_and_scale(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform(x_mm=-4.0, y_mm=0.0, scale=0.5))
    spy = QSignalSpy(controls.transform_changed)
    controls._y_slider.setValue(mm_to_position_slider(-10.0, 217.9))
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
    controls.set_work_area_dimensions(297.0, 210.0)
    assert controls._x_spin.value() == pytest.approx(40.0)
    assert controls._y_spin.value() == pytest.approx(-5.0)
    assert controls._x_slider.maximum() == mm_to_position_slider(297.0, 297.0)
    assert position_slider_to_mm(controls._x_slider.value(), 297.0) == pytest.approx(40.0, abs=0.05)


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
    window._artwork_controls._x_slider.setValue(
        mm_to_position_slider(3.0, window._artwork_controls._x_range_mm),
    )
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
    assert window._artwork_controls._x_range_mm == pytest.approx(area.width_mm)
    assert window._artwork_controls._y_range_mm == pytest.approx(area.height_mm)
    window.close()


def test_programmatic_transform_updates_controls(qapp) -> None:
    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    window._set_artwork_transform(ArtworkTransform(x_mm=5.0, y_mm=-2.0, scale=2.0))
    assert window._artwork_controls._x_spin.value() == pytest.approx(5.0)
    assert window._artwork_controls._scale_spin.value() == pytest.approx(200.0)
    window.close()
