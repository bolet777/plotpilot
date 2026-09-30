"""Canonical SVG page geometry parsing and unit mapping."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from svgelements import SVG

from plotpilot.geometry.plot_viewport import _SvgToMm, prepare_positioned_plot_svg
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plot_service import plot_svg_for_layer
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.svg.page_geometry import CSS_PX_TO_MM, parse_page_geometry

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden"


@pytest.mark.parametrize(
    ("width", "height", "expected_w_mm", "expected_h_mm"),
    [
        ("100mm", "50mm", 100.0, 50.0),
        ("10cm", "5cm", 100.0, 50.0),
        ("4in", "2in", 4 * 25.4, 2 * 25.4),
        ("72pt", "36pt", 72 * 25.4 / 72, 36 * 25.4 / 72),
        ("96px", "48px", 96 * CSS_PX_TO_MM, 48 * CSS_PX_TO_MM),
        ("100", "200", 100 * CSS_PX_TO_MM, 200 * CSS_PX_TO_MM),
    ],
)
def test_physical_units_from_root(
    width: str,
    height: str,
    expected_w_mm: float,
    expected_h_mm: float,
) -> None:
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"></svg>'
    page = parse_page_geometry(svg)
    assert page.width_mm == pytest.approx(expected_w_mm)
    assert page.height_mm == pytest.approx(expected_h_mm)
    assert page.viewbox is None


def test_root_viewbox_parsed_from_element_not_nested() -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">
  <defs><marker id="m" viewBox="0 0 200 200"/></defs>
</svg>"""
    page = parse_page_geometry(svg)
    assert page.viewbox is None


def test_non_zero_viewbox_origin() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
        'viewBox="10 20 80 60"></svg>'
    )
    page = parse_page_geometry(svg)
    assert page.viewbox == pytest.approx((10.0, 20.0, 80.0, 60.0))


def test_viewboxless_maps_user_units_as_css_px() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm">'
        '<path d="M 10 10 L 110 60" stroke="black"/></svg>'
    )
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=400.0,
        viewport_height_mm=300.0,
        transform=ArtworkTransform.identity(),
    )
    assert "M" in prepared.svg_text
    page = parse_page_geometry(svg)
    assert page.viewbox is None
    assert page.user_point_to_mm(10.0, 10.0) == pytest.approx(
        (10 * CSS_PX_TO_MM, 10 * CSS_PX_TO_MM),
    )


def test_isolated_layer_matches_document_page_geometry() -> None:
    document = load_svg_from_path(GOLDEN / "layers" / "b5_px_inkscape_layer.svg")
    layer = next(layer for layer in layers_for_document(document) if layer.name == "L")
    isolated = plot_svg_for_layer(document, layer)
    whole = parse_page_geometry(document.raw_text)
    iso = parse_page_geometry(isolated)
    assert iso.width_mm == pytest.approx(whole.width_mm)
    assert iso.height_mm == pytest.approx(whole.height_mm)
    assert iso.viewbox == whole.viewbox


def test_svgelements_viewbox_pipeline_uses_viewport_pixels() -> None:
    svg = (
        '<?xml version="1.0"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
        'viewBox="0 0 100 100">'
        '<path d="M 10 10 L 90 10" stroke="black"/></svg>'
    )
    page = parse_page_geometry(svg)
    root = SVG.parse(io.StringIO(svg))
    to_mm = _SvgToMm.from_page(page, root)
    # svgelements reports viewport pixels along the 100mm edge.
    x_mm, _y_mm = to_mm.point(37.795296, 37.795296)
    assert x_mm == pytest.approx(10.0, abs=0.02)
