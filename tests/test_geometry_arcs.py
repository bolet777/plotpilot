"""Arc flattening quality (B2) and sampling invariants."""

from __future__ import annotations

import math

import pytest

from golden_oracle import parse_prepared_polylines, polyline_bbox
from plotpilot.geometry.plot_viewport import prepare_positioned_plot_svg
from plotpilot.models.artwork_transform import ArtworkTransform


def _prepare(
    svg: str,
    *,
    viewport: tuple[float, float] = (100.0, 100.0),
    transform: ArtworkTransform | None = None,
) -> list[list[tuple[float, float]]]:
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=viewport[0],
        viewport_height_mm=viewport[1],
        transform=transform or ArtworkTransform.identity(),
    )
    return parse_prepared_polylines(prepared.svg_text)


def _circle_offenders(
    polylines: list[list[tuple[float, float]]],
    *,
    cx: float,
    cy: float,
    radius: float,
    radial_tol: float = 0.15,
) -> list[tuple[float, float]]:
    bad: list[tuple[float, float]] = []
    for polyline in polylines:
        for x, y in polyline:
            if abs(math.hypot(x - cx, y - cy) - radius) > radial_tol:
                bad.append((x, y))
    return bad


def _arc_svg(d: str, *, page: float = 100.0) -> str:
    ns = "http://www.w3.org/2000/svg"
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="{ns}" width="{page}mm" height="{page}mm" '
        f'viewBox="0 0 {page} {page}">\n'
        f'  <path d="{d}" fill="none" stroke="black"/>\n'
        f"</svg>"
    )


def test_arc_90_degree_circular_quarter() -> None:
    svg = _arc_svg("M 50 30 A 20 20 0 0 1 70 50")
    polylines = _prepare(svg)
    assert len(polylines) == 1
    assert len(polylines[0]) >= 8
    assert polyline_bbox(polylines) == pytest.approx((50.0, 30.0, 70.0, 50.0), abs=0.5)


def test_arc_180_degree_semicircle() -> None:
    svg = _arc_svg("M 30 50 A 20 20 0 1 0 70 50")
    polylines = _prepare(svg)
    assert len(polylines) == 1
    assert len(polylines[0]) >= 15
    xmin, ymin, xmax, ymax = polyline_bbox(polylines)
    assert xmin == pytest.approx(30.0, abs=0.5)
    assert xmax == pytest.approx(70.0, abs=0.5)
    assert ymax == pytest.approx(70.0, abs=0.5)


def test_arc_large_arc_over_180_degrees() -> None:
    svg = _arc_svg("M 30 50 A 20 20 0 1 0 70 50")
    polylines = _prepare(svg)
    assert len(polylines) == 1
    assert len(polylines[0]) >= 30


def test_arc_near_360_b2_reproduction() -> None:
    svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M 70 50 A 20 20 0 1 1 69.999 50.02" fill="none" stroke="black"/>
</svg>"""
    polylines = _prepare(svg)
    point_count = sum(len(line) for line in polylines)
    assert point_count >= 30
    cx, cy, r = 89.974544, 51.008752, 20.0
    assert not _circle_offenders(polylines, cx=cx, cy=cy, radius=r, radial_tol=0.2)


def test_arc_sweep_zero_vs_one_differ() -> None:
    sweep0 = _arc_svg("M 20 50 A 20 20 0 0 0 80 50")
    sweep1 = _arc_svg("M 20 50 A 20 20 0 0 1 80 50")
    bbox0 = polyline_bbox(_prepare(sweep0))
    bbox1 = polyline_bbox(_prepare(sweep1))
    assert bbox0 != pytest.approx(bbox1, abs=0.01)


def test_elliptical_arc_rx_not_equal_ry() -> None:
    svg = _arc_svg("M 20 50 A 30 10 0 0 1 80 50")
    polylines = _prepare(svg)
    assert len(polylines[0]) >= 10
    xmin, ymin, xmax, ymax = polyline_bbox(polylines)
    assert xmax - xmin == pytest.approx(60.0, abs=1.0)
    assert ymax - ymin == pytest.approx(10.0, abs=2.0)


def test_translated_arc() -> None:
    svg = _arc_svg("M 70 50 A 20 20 0 0 1 90 50")
    polylines = _prepare(
        svg,
        transform=ArtworkTransform(x_mm=10.0, y_mm=5.0, scale=1.0),
    )
    xmin, ymin, xmax, ymax = polyline_bbox(polylines)
    assert xmin == pytest.approx(80.0, abs=0.5)
    assert ymin == pytest.approx(52.0, abs=1.0)


def test_scaled_arc() -> None:
    svg = _arc_svg("M 50 30 A 20 20 0 0 1 70 50")
    polylines = _prepare(
        svg,
        viewport=(200.0, 200.0),
        transform=ArtworkTransform(scale=2.0),
    )
    xmin, ymin, xmax, ymax = polyline_bbox(polylines)
    assert xmin == pytest.approx(100.0, abs=1.0)
    assert ymax == pytest.approx(100.0, abs=1.0)


def test_arc_partially_clipped_by_viewport() -> None:
    svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M 70 50 A 20 20 0 1 1 69.999 50.02" fill="none" stroke="black"/>
</svg>"""
    polylines = _prepare(svg, viewport=(100.0, 100.0))
    xmin, ymin, xmax, ymax = polyline_bbox(polylines)
    assert xmax == pytest.approx(100.0, abs=0.05)
    assert xmin == pytest.approx(69.975, abs=0.2)
