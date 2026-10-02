"""Preview context ghost: drawn from the same flattened geometry as the clipped ink.

Regression for the "two offset copies" artefact: the ghost used to be the source
SVG rendered by QSvgRenderer (stretched viewBox, live transform) while the ink
came from svgelements geometry (spec-correct ``xMidYMid meet``) computed
asynchronously. Both now derive from ``PreparedLayerGeometry.polylines`` and the
stale ink is hidden while a clip refresh is pending.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QThreadPool
from PySide6.QtGui import QColor

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.preview_work_area import PreviewWorkArea
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow
from plotpilot.ui.preview_widget import LayerPreviewWidget

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="100mm" '
    'viewBox="0 0 200 100"><path d="M0 50 L200 50" stroke="#000" fill="none"/></svg>'
)
_LINE = (((0.0, 50.0), (200.0, 50.0)),)


def _wait_for_clip(window: MainWindow, qapp, *, timeout_s: float = 5.0) -> None:
    """Pump events while letting the worker thread hold the GIL (no busy qWait loop)."""
    deadline = time.monotonic() + timeout_s
    preview = window._preview
    while time.monotonic() < deadline:
        qapp.processEvents()
        if (
            not window._preview_prep_timer.isActive()
            and QThreadPool.globalInstance().activeThreadCount() == 0
            and not preview.clip_pending
        ):
            qapp.processEvents()
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for the preview clip")


def _widget(qapp) -> LayerPreviewWidget:
    widget = LayerPreviewWidget()
    widget.resize(700, 400)
    widget.set_rulers_visible(False)
    widget.show()
    qapp.processEvents()
    assert widget.set_preview_svg(_SVG)
    widget.set_work_area_overlay(
        svg_width_mm=200.0,
        svg_height_mm=100.0,
        work_area=PreviewWorkArea(200.0, 100.0, "Test", False),
    )
    return widget


def _luma_at_mm(widget: LayerPreviewWidget, x_mm: float, y_mm: float) -> int:
    layout = widget.physical_layout
    assert layout is not None
    px = QPoint(
        round(layout.workspace_x_px + x_mm * layout.mm_to_px),
        round(layout.workspace_y_px + y_mm * layout.mm_to_px),
    )
    image = widget.grab().toImage()
    return QColor(image.pixel(px)).lightness()


def test_context_polylines_switch_ghost_source(qapp) -> None:
    widget = _widget(qapp)
    assert widget.uses_geometry_context is False
    widget.set_context_polylines(_LINE)
    assert widget.uses_geometry_context is True
    assert widget.context_polylines == _LINE
    widget.set_context_polylines(None)
    assert widget.uses_geometry_context is False


def test_new_source_svg_drops_stale_context_polylines(qapp) -> None:
    widget = _widget(qapp)
    widget.set_context_polylines(_LINE)
    assert widget.set_preview_svg(_SVG)  # same text → keep
    assert widget.uses_geometry_context is True
    assert widget.set_preview_svg(_SVG.replace("M0 50", "M0 40"))
    assert widget.uses_geometry_context is False


def test_pending_hides_stale_ink_and_shows_ghost_at_live_transform(qapp) -> None:
    widget = _widget(qapp)
    widget.set_context_polylines(_LINE)
    widget.set_clipped_plot(polylines=_LINE, error_message=None)
    paper = _luma_at_mm(widget, 100.0, 25.0)
    ink = _luma_at_mm(widget, 100.0, 50.0)
    assert ink < paper - 60  # solid ink on the line

    # Move the artwork down 20 mm; the clip is now stale and pending.
    widget.set_artwork_transform(ArtworkTransform(x_mm=0.0, y_mm=20.0, scale=1.0))
    widget.set_clip_pending()
    assert widget.clip_pending is True
    stale = _luma_at_mm(widget, 100.0, 50.0)
    ghost = _luma_at_mm(widget, 100.0, 70.0)
    assert stale > paper - 12  # old ink position is clean
    assert paper - 90 < ghost < paper - 15  # translucent ghost at the new position

    # Clip result arrives → pending cleared, ink back.
    moved = (((0.0, 70.0), (200.0, 70.0)),)
    widget.set_clipped_plot(polylines=moved, error_message=None)
    assert widget.clip_pending is False
    assert _luma_at_mm(widget, 100.0, 70.0) < paper - 60


def test_ghost_scales_with_artwork_transform(qapp) -> None:
    widget = _widget(qapp)
    widget.set_context_polylines(_LINE)
    widget.set_clip_pending()
    widget.set_artwork_transform(ArtworkTransform(x_mm=0.0, y_mm=0.0, scale=0.5))
    paper = _luma_at_mm(widget, 150.0, 10.0)
    assert _luma_at_mm(widget, 50.0, 25.0) < paper - 15  # line now at y = 25 mm, x ≤ 100
    assert _luma_at_mm(widget, 150.0, 25.0) > paper - 12  # beyond the scaled extent
    assert _luma_at_mm(widget, 50.0, 50.0) > paper - 12  # nothing at the old position


def test_window_feeds_geometry_context_and_clears_pending(qapp) -> None:
    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    window.resize(1000, 700)
    window.show()
    window.set_document(load_svg_from_path(FIXTURES / "aspect_mismatch_viewbox.svg"))
    preview = window._preview
    _wait_for_clip(window, qapp)
    assert preview.uses_geometry_context is True

    # The page is 300 × 200 mm with a square viewBox: per the SVG spec the content
    # is uniformly scaled to 200 mm and centred, so the 10..90 rect maps to
    # x 70..230 and y 20..180 — the same numbers the plot geometry uses.
    xs = [x for path in preview.context_polylines for x, _ in path]
    ys = [y for path in preview.context_polylines for _, y in path]
    assert min(xs) == pytest.approx(70.0, abs=0.5)
    assert max(xs) == pytest.approx(230.0, abs=0.5)
    assert min(ys) == pytest.approx(20.0, abs=0.5)
    assert max(ys) == pytest.approx(180.0, abs=0.5)
    clipped_xs = [x for path in preview.clipped_polylines for x, _ in path]
    assert min(clipped_xs) >= 70.0 - 0.5
    assert max(clipped_xs) <= 230.0 + 0.5

    # A transform change marks the clip pending, then the recompute clears it.
    window._set_artwork_transform(ArtworkTransform(x_mm=5.0, y_mm=0.0, scale=1.0))
    assert preview.clip_pending is True
    _wait_for_clip(window, qapp)
    assert preview.uses_geometry_context is True
    window.close()
