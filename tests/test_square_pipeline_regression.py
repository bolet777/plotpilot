"""Regression: closed squares must survive the plot preparation pipeline."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from svgelements import SVG, Line

from plotpilot.geometry.plot_viewport import (
    _SvgToMm,
    _parse_path_d_coords,
    _read_viewbox_user,
    prepare_positioned_plot_svg,
)
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plot_service import plot_svg_for_layer
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.svg.plot_dimensions import parse_physical_size

FIXTURES = Path(__file__).resolve().parent / "fixtures"

SQUARE_PATH = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M 10 10 L 90 10 L 90 90 L 10 90 Z" fill="none" stroke="black"/>
</svg>"""

SQUARE_RECT = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <rect x="10" y="10" width="80" height="80" fill="none" stroke="black"/>
</svg>"""

SQUARE_POLYGON = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <polygon points="10,10 90,10 90,90 10,90" fill="none" stroke="black"/>
</svg>"""

A4_CENTERED_RECT = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">
  <rect x="65" y="108.5" width="80" height="80" fill="none" stroke="black"/>
</svg>"""

EXPECTED_SQUARE_MM = [(10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0), (10.0, 10.0)]


def _path_coords_from_svg(svg_text: str) -> list[tuple[float, float]]:
    match = re.search(r'd="([^"]+)"', svg_text)
    assert match is not None
    return _parse_path_d_coords(match.group(1))


def _bbox(coords: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return min(xs), min(ys), max(xs), max(ys)


def _assert_square_coords(coords: list[tuple[float, float]]) -> None:
    assert len(coords) == 5
    for actual, expected in zip(coords, EXPECTED_SQUARE_MM, strict=True):
        assert actual == pytest.approx(expected, abs=0.02)


@pytest.mark.parametrize(
    "source_svg",
    [SQUARE_PATH, SQUARE_RECT, SQUARE_POLYGON],
    ids=["path", "rect", "polygon"],
)
def test_identity_pipeline_preserves_closed_square(source_svg: str) -> None:
    prepared = prepare_positioned_plot_svg(
        source_svg,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
    )
    coords = _path_coords_from_svg(prepared.svg_text)
    _assert_square_coords(coords)
    assert prepared.path_count == 1
    assert _bbox(coords) == pytest.approx((10.0, 10.0, 90.0, 90.0), abs=0.02)


def test_square_pipeline_stages_via_layer_isolation() -> None:
    document = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    layer = layers_for_document(document)[0]
    isolated = plot_svg_for_layer(document, layer)
    prepared = prepare_layer_plot_svg(
        isolated,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )

    for svg_text in (document.raw_text, isolated):
        page = parse_physical_size(svg_text)
        viewbox = _read_viewbox_user(svg_text, page.width_mm, page.height_mm)
        assert page.width_mm == pytest.approx(100.0)
        assert viewbox[2:] == pytest.approx((100.0, 100.0))

    _assert_square_coords(_path_coords_from_svg(prepared.svg_text))


def test_svgelements_viewbox_semantics_documented_by_mm_mapping() -> None:
    """With viewBox, segment coords are root pixels; mapper must yield viewBox user mm."""
    page = parse_physical_size(SQUARE_PATH)
    viewbox = _read_viewbox_user(SQUARE_PATH, page.width_mm, page.height_mm)
    root = SVG.parse(io.StringIO(SQUARE_PATH))
    to_mm = _SvgToMm.from_root(page.width_mm, page.height_mm, viewbox, root)
    assert to_mm.coordinates_in_viewport_pixels is True
    for element in root.elements():
        if not hasattr(element, "segments"):
            continue
        lines = [
            segment
            for segment in element.segments(transformed=True)
            if isinstance(segment, Line)
        ]
        assert lines
        first = lines[0]
        # Raw svgelements coords are root pixels, not viewBox user units (10, 10).
        assert first.start.x == pytest.approx(37.795296, rel=1e-4)
        assert to_mm.point(first.start.x, first.start.y) == pytest.approx(
            (10.0, 10.0),
            abs=0.02,
        )


@pytest.mark.parametrize(
    ("svg_text", "expected_end_x_mm"),
    [
        (
            '<svg width="210mm" height="297mm" viewBox="0 0 210 297">'
            '<path d="M 10 10 L 200 10" stroke="black"/></svg>',
            200.0,
        ),
        (
            '<svg width="210mm" height="297mm" viewBox="0 0 794 1123">'
            '<path d="M 10 10 L 90 10" stroke="black"/></svg>',
            23.81,
        ),
    ],
)
def test_viewbox_physical_size_combinations(svg_text: str, expected_end_x_mm: float) -> None:
    prepared = prepare_positioned_plot_svg(
        f'<?xml version="1.0"?>{svg_text}',
        viewport_width_mm=420.0,
        viewport_height_mm=297.0,
        transform=ArtworkTransform.identity(),
    )
    coords = _path_coords_from_svg(prepared.svg_text)
    assert coords[-1][0] == pytest.approx(expected_end_x_mm, abs=0.05)


def test_viewboxless_large_coordinates_use_viewport_pixels() -> None:
    """DrawingBot-style exports: no viewBox but transformed coords exceed page user width."""
    svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm">
  <path d="M 112.25 79.71 L 900.5 150.2" stroke="#312b2b"/>
</svg>"""
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=299.974,
        viewport_height_mm=217.932,
        transform=ArtworkTransform.identity(),
    )
    coords = _path_coords_from_svg(prepared.svg_text)
    assert coords[0][0] == pytest.approx(29.69, abs=0.05)
    assert coords[-1][0] == pytest.approx(238.2, abs=0.2)


def test_a4_centered_rectangle_identity() -> None:
    prepared = prepare_positioned_plot_svg(
        A4_CENTERED_RECT,
        viewport_width_mm=420.0,
        viewport_height_mm=297.0,
        transform=ArtworkTransform.identity(),
    )
    coords = _path_coords_from_svg(prepared.svg_text)
    assert _bbox(coords) == pytest.approx((65.0, 108.5, 145.0, 188.5), abs=0.05)


def test_closed_square_has_four_sides_after_clipping() -> None:
    prepared = prepare_positioned_plot_svg(
        SQUARE_PATH,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
    )
    coords = _path_coords_from_svg(prepared.svg_text)
    edges = list(zip(coords, coords[1:], strict=False))
    assert len(edges) == 4
    expected_edges = (
        ((10.0, 10.0), (90.0, 10.0)),
        ((90.0, 10.0), (90.0, 90.0)),
        ((90.0, 90.0), (10.0, 90.0)),
        ((10.0, 90.0), (10.0, 10.0)),
    )
    for edge, expected in zip(edges, expected_edges, strict=True):
        assert edge[0] == pytest.approx(expected[0], abs=0.02)
        assert edge[1] == pytest.approx(expected[1], abs=0.02)
