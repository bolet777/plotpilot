"""Preview plotter work-area overlay (mm-space layout)."""

from __future__ import annotations

import pytest

from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_model import get_plotter_model_info
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    compute_physical_preview_layout,
    mm_rect_to_px,
    preview_work_area_is_ambiguous,
    resolve_preview_work_area,
)
from plotpilot.ui.preview_widget import LayerPreviewWidget, fit_rect_preserve_aspect

_INCH = 25.4


def _ratio(w: float, h: float) -> float:
    return w / h


def test_model_1_resolves_plotter_travel() -> None:
    area = resolve_preview_work_area(PlotSettings(model=1))
    assert area is not None
    info = get_plotter_model_info(1)
    assert area.width_mm == pytest.approx(info.max_width_mm)
    assert area.height_mm == pytest.approx(info.max_height_mm)
    assert not area.from_fallback


def test_model_2_resolves_plotter_travel() -> None:
    area = resolve_preview_work_area(PlotSettings(model=2))
    assert area is not None
    info = get_plotter_model_info(2)
    assert area.width_mm == pytest.approx(16.93 * _INCH)
    assert area.height_mm == pytest.approx(11.69 * _INCH)
    assert info.display_name in area.label


@pytest.mark.parametrize("code", range(1, 8))
def test_explicit_models_use_plotter_model_info(code: int) -> None:
    area = resolve_preview_work_area(PlotSettings(model=code))
    info = get_plotter_model_info(code)
    assert area is not None
    assert area.width_mm == pytest.approx(info.max_width_mm)
    assert area.height_mm == pytest.approx(info.max_height_mm)


def test_default_cli_is_ambiguous() -> None:
    assert preview_work_area_is_ambiguous(PlotSettings())
    area = resolve_preview_work_area(PlotSettings(), fallback=FallbackWorkArea.A4)
    assert area is not None
    assert area.from_fallback


def test_a4_fallback_dimensions() -> None:
    area = resolve_preview_work_area(PlotSettings(), fallback=FallbackWorkArea.A4)
    assert area is not None
    assert area.width_mm == pytest.approx(210.0)
    assert area.height_mm == pytest.approx(297.0)


def test_a3_fallback_dimensions() -> None:
    area = resolve_preview_work_area(PlotSettings(), fallback=FallbackWorkArea.A3)
    assert area is not None
    assert area.width_mm == pytest.approx(297.0)
    assert area.height_mm == pytest.approx(420.0)


def test_shared_transform_maps_svg_and_work_area() -> None:
    layout = compute_physical_preview_layout(210.0, 297.0, 430.0, 297.0, 800.0, 600.0)
    assert layout is not None
    assert layout.workspace_width_mm == pytest.approx(430.0)
    assert layout.workspace_height_mm == pytest.approx(297.0)
    _, _, svg_w, _ = mm_rect_to_px(layout, layout.svg_rect_mm)
    _, _, work_w, _ = mm_rect_to_px(layout, layout.work_area_rect_mm)
    assert svg_w / work_w == pytest.approx(210.0 / 430.0, rel=1e-9)


def test_resize_preserves_plotter_aspect_ratio() -> None:
    work_w_mm, work_h_mm = 430.0, 297.0
    for w, h in ((400, 300), (120, 900), (900, 120)):
        layout = compute_physical_preview_layout(210.0, 297.0, work_w_mm, work_h_mm, w, h)
        assert layout is not None
        _, _, pw, ph = mm_rect_to_px(layout, layout.work_area_rect_mm)
        assert _ratio(pw, ph) == pytest.approx(_ratio(work_w_mm, work_h_mm), rel=1e-9)


def test_resize_preserves_svg_aspect_ratio() -> None:
    svg_w_mm, svg_h_mm = 210.0, 297.0
    for w, h in ((400, 300), (120, 900), (900, 120)):
        layout = compute_physical_preview_layout(svg_w_mm, svg_h_mm, 430.0, 297.0, w, h)
        assert layout is not None
        _, _, sw, sh = mm_rect_to_px(layout, layout.svg_rect_mm)
        assert _ratio(sw, sh) == pytest.approx(_ratio(svg_w_mm, svg_h_mm), rel=1e-9)


def test_relative_svg_to_work_area_scale_constant_across_resize() -> None:
    svg_w_mm, work_w_mm = 210.0, 430.0
    ratios: list[float] = []
    for w, h in ((640, 480), (200, 800), (50, 50)):
        layout = compute_physical_preview_layout(svg_w_mm, 297.0, work_w_mm, 297.0, w, h)
        assert layout is not None
        _, _, sw, _ = mm_rect_to_px(layout, layout.svg_rect_mm)
        _, _, ww, _ = mm_rect_to_px(layout, layout.work_area_rect_mm)
        ratios.append(sw / ww)
    assert ratios[0] == pytest.approx(svg_w_mm / work_w_mm, rel=1e-9)
    assert ratios[1] == pytest.approx(ratios[0], rel=1e-9)
    assert ratios[2] == pytest.approx(ratios[0], rel=1e-9)


def test_svg_smaller_than_machine_fits_inside_work_area() -> None:
    layout = compute_physical_preview_layout(210.0, 297.0, 430.0, 297.0, 500.0, 400.0)
    assert layout is not None
    sx, sy, sw, sh = mm_rect_to_px(layout, layout.svg_rect_mm)
    wx, wy, ww, wh = mm_rect_to_px(layout, layout.work_area_rect_mm)
    assert sx >= wx - 1e-9
    assert sy >= wy - 1e-9
    assert sx + sw <= wx + ww + 1e-9
    assert sy + sh <= wy + wh + 1e-9


def test_svg_larger_than_machine_extends_beyond_work_area() -> None:
    layout = compute_physical_preview_layout(500.0, 500.0, 300.0, 200.0, 500.0, 400.0)
    assert layout is not None
    sx, sy, sw, sh = mm_rect_to_px(layout, layout.svg_rect_mm)
    wx, wy, ww, wh = mm_rect_to_px(layout, layout.work_area_rect_mm)
    assert sx + sw > wx + ww + 1e-9 or sy + sh > wy + wh + 1e-9


def test_landscape_machine_stays_landscape_on_screen() -> None:
    layout = compute_physical_preview_layout(210.0, 297.0, 430.0, 297.0, 600.0, 600.0)
    assert layout is not None
    _, _, ww, wh = mm_rect_to_px(layout, layout.work_area_rect_mm)
    assert ww > wh


def test_portrait_document_not_rotated_in_layout() -> None:
    layout = compute_physical_preview_layout(210.0, 297.0, 430.0, 297.0, 600.0, 600.0)
    assert layout is not None
    assert layout.svg_rect_mm.width_mm == pytest.approx(210.0)
    assert layout.svg_rect_mm.height_mm == pytest.approx(297.0)


A4_SVG = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">
  <rect width="210" height="297" fill="#ffffff"/>
  <path d="M10 10 L200 280" stroke="#000"/>
</svg>"""


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def test_widget_overlay_does_not_modify_source_svg(qapp) -> None:
    widget = LayerPreviewWidget()
    assert widget.set_preview_svg(A4_SVG) is True
    area = resolve_preview_work_area(PlotSettings(model=1))
    widget.set_work_area_overlay(svg_width_mm=210.0, svg_height_mm=297.0, work_area=area)
    assert widget.last_svg == A4_SVG
    assert "cc0000" not in widget.last_svg.lower()


def test_widget_physical_layout_updates_with_resize(qapp) -> None:
    widget = LayerPreviewWidget()
    widget.resize(640, 480)
    widget.set_preview_svg(A4_SVG)
    area = resolve_preview_work_area(PlotSettings(model=2))
    widget.set_work_area_overlay(svg_width_mm=210.0, svg_height_mm=297.0, work_area=area)

    first = widget.physical_layout
    assert first is not None
    widget.resize(200, 500)
    second = widget.physical_layout
    assert second is not None
    assert second.mm_to_px != first.mm_to_px
    _, _, w1, h1 = mm_rect_to_px(first, first.work_area_rect_mm)
    _, _, w2, h2 = mm_rect_to_px(second, second.work_area_rect_mm)
    assert _ratio(w1, h1) == pytest.approx(_ratio(w2, h2), rel=1e-9)


def test_legacy_fit_still_used_without_overlay(qapp) -> None:
    widget = LayerPreviewWidget()
    widget.resize(400, 300)
    widget.set_preview_svg(A4_SVG)
    layout_before = fit_rect_preserve_aspect(210.0, 297.0, widget._available_rect())  # noqa: SLF001
    widget.set_work_area_overlay(svg_width_mm=0, svg_height_mm=0, work_area=None)
    assert widget.physical_layout is None
    layout_after = fit_rect_preserve_aspect(210.0, 297.0, widget._available_rect())  # noqa: SLF001
    assert layout_before.width() == pytest.approx(layout_after.width())
