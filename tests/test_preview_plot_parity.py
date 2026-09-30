"""Preview must use the same prepared geometry as plot output."""

from __future__ import annotations

from pathlib import Path

import pytest

from golden_oracle import parse_prepared_polylines, polyline_bbox
from plotpilot.geometry.plot_viewport import prepare_positioned_plot_svg
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plot_service import plot_svg_for_layer
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.preview_prepared_service import build_prepared_layer_preview
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.svg.page_geometry import CSS_PX_TO_MM

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = FIXTURES / "golden"


def _bbox_from_prepared(svg_text: str) -> tuple[float, float, float, float]:
    polylines = parse_prepared_polylines(svg_text)
    return polyline_bbox(polylines)


B4_VIEWBOXLESS_RECT = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm">
  <rect x="10" y="10" width="100" height="50" fill="none" stroke="black"/>
</svg>"""

B9_PRESERVE_ASPECT = (GOLDEN / "viewbox" / "b9_preserve_aspect_meet.svg").read_text(
    encoding="utf-8",
)


def test_prepared_preview_matches_prepare_layer_plot_svg() -> None:
    document = load_svg_from_path(GOLDEN / "layers" / "b5_px_inkscape_layer.svg")
    layer = next(item for item in layers_for_document(document) if item.name == "L")
    preview = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    assert preview.prepared is not None
    direct = prepare_layer_plot_svg(
        preview.context_svg_text,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    assert preview.prepared.svg_text == direct.svg_text
    assert preview.prepared.path_count == direct.path_count


def test_b4_viewboxless_preview_bbox_matches_plot() -> None:
    prepared = prepare_positioned_plot_svg(
        B4_VIEWBOXLESS_RECT,
        viewport_width_mm=400.0,
        viewport_height_mm=300.0,
        transform=ArtworkTransform.identity(),
    )
    x0 = 10 * CSS_PX_TO_MM
    y0 = 10 * CSS_PX_TO_MM
    x1 = 110 * CSS_PX_TO_MM
    y1 = 60 * CSS_PX_TO_MM
    assert _bbox_from_prepared(prepared.svg_text) == pytest.approx(
        (x0, y0, x1, y1),
        abs=0.05,
    )


def test_b9_preserve_aspect_preview_bbox_matches_plot() -> None:
    prepared = prepare_positioned_plot_svg(
        B9_PRESERVE_ASPECT,
        viewport_width_mm=200.0,
        viewport_height_mm=150.0,
        transform=ArtworkTransform.identity(),
    )
    assert _bbox_from_prepared(prepared.svg_text) == pytest.approx(
        (50.0, 0.0, 150.0, 100.0),
        abs=0.02,
    )


def test_clipped_geometry_ends_at_viewport() -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M -20 50 L 120 50" stroke="black"/>
</svg>"""
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
    )
    polylines = parse_prepared_polylines(prepared.svg_text)
    points = [point for polyline in polylines for point in polyline]
    xs = [point[0] for point in points]
    assert min(xs) == pytest.approx(0.0, abs=0.02)
    assert max(xs) == pytest.approx(100.0, abs=0.02)


def test_layer_switch_rebuilds_prepared_preview() -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert len(layers) >= 2
    first = build_prepared_layer_preview(
        document,
        layers[0],
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    second = build_prepared_layer_preview(
        document,
        layers[1],
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    assert first.prepared is not None
    assert second.prepared is not None
    assert first.context_svg_text != second.context_svg_text
    assert first.prepared.svg_text != second.prepared.svg_text


def test_transform_changes_prepared_output() -> None:
    document = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    layer = layers_for_document(document)[0]
    identity = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    shifted = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform(x_mm=10.0, y_mm=5.0, scale=1.0),
    )
    assert identity.prepared is not None
    assert shifted.prepared is not None
    assert identity.prepared.svg_text != shifted.prepared.svg_text


def test_machine_model_change_recomputes_preview() -> None:
    document = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    layer = layers_for_document(document)[0]
    small = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    large = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=PlotSettings(model=2),
        transform=ArtworkTransform.identity(),
    )
    assert small.prepared is not None
    assert large.prepared is not None
    assert small.prepared.width_mm != large.prepared.width_mm


def test_source_document_unchanged_by_preview_build() -> None:
    document = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    raw_before = document.raw_text
    layer = layers_for_document(document)[0]
    _ = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    assert document.raw_text == raw_before
    isolated = plot_svg_for_layer(document, layer)
    _ = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    assert plot_svg_for_layer(document, layer) == isolated


def test_text_triggers_unplottable_warning(tmp_path: Path) -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <text x="10" y="50">Hello</text>
  <path d="M 10 10 L 90 90" stroke="black"/>
</svg>"""
    path = tmp_path / "text.svg"
    path.write_text(svg, encoding="utf-8")
    document = load_svg_from_path(path)
    layer = layers_for_document(document)[0]
    preview = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    assert preview.prepared is not None
    assert any("Text will not be plotted" in line for line in preview.status_lines)


def test_golden_parity_preview_equals_prepared_plot_svg() -> None:
    """Structural invariant: preview service uses the same prepared SVG as plotting."""
    document = load_svg_from_path(GOLDEN / "viewbox" / "b9_preserve_aspect_meet.svg")
    layer = layers_for_document(document)[0]
    preview = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    plot_svg = prepare_layer_plot_svg(
        plot_svg_for_layer(document, layer),
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    assert preview.prepared is not None
    assert parse_prepared_polylines(preview.prepared.svg_text) == parse_prepared_polylines(
        plot_svg.svg_text,
    )
