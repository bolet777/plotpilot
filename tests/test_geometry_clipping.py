"""Liang–Barsky segment clipping and path splitting."""

from __future__ import annotations

import pytest

from golden_oracle import parse_prepared_polylines
from plotpilot.geometry.liang_barsky import ClipRect, clip_segment
from plotpilot.geometry.plot_viewport import prepare_positioned_plot_svg
from plotpilot.models.artwork_transform import ArtworkTransform

_RECT = ClipRect(0.0, 0.0, 100.0, 100.0)
_VIEWPORT = (100.0, 100.0)
_TOL = 0.02


def _prepare_polylines(
    svg: str,
    *,
    viewport: tuple[float, float] = _VIEWPORT,
    transform: ArtworkTransform | None = None,
) -> list[list[tuple[float, float]]]:
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=viewport[0],
        viewport_height_mm=viewport[1],
        transform=transform or ArtworkTransform.identity(),
    )
    return parse_prepared_polylines(prepared.svg_text)


def _assert_inside_viewport(
    polylines: list[list[tuple[float, float]]],
    *,
    width: float = 100.0,
    height: float = 100.0,
    tolerance: float = _TOL,
) -> None:
    for polyline in polylines:
        for x, y in polyline:
            assert -tolerance <= x <= width + tolerance
            assert -tolerance <= y <= height + tolerance


def _assert_no_diagonal_bridge(
    polylines: list[list[tuple[float, float]]],
    forbidden: tuple[tuple[float, float], tuple[float, float]],
) -> None:
    start, end = forbidden
    for polyline in polylines:
        for a, b in zip(polyline, polyline[1:], strict=False):
            if _segment_matches(a, b, start, end):
                msg = f"invented bridge {a} -> {b}"
                raise AssertionError(msg)


def _segment_matches(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
) -> bool:
    return (_near(a0, b0) and _near(a1, b1)) or (_near(a0, b1) and _near(a1, b0))


def _near(a: tuple[float, float], b: tuple[float, float], tol: float = _TOL) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


@pytest.mark.parametrize(
    ("x0", "y0", "x1", "y1", "accept", "ex0", "ey0", "ex1", "ey1"),
    [
        (10.0, 10.0, 20.0, 20.0, True, 10.0, 10.0, 20.0, 20.0),
        (-10.0, 50.0, -5.0, 50.0, False, -10.0, 50.0, -5.0, 50.0),
        (-10.0, 50.0, 110.0, 50.0, True, 0.0, 50.0, 100.0, 50.0),
        (50.0, -10.0, 50.0, 110.0, True, 50.0, 0.0, 50.0, 100.0),
        (50.0, 50.0, 150.0, 50.0, True, 50.0, 50.0, 100.0, 50.0),
        (0.0, 0.0, 0.0, 0.0, True, 0.0, 0.0, 0.0, 0.0),
    ],
)
def test_clip_segment_cases(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    accept: bool,
    ex0: float,
    ey0: float,
    ex1: float,
    ey1: float,
) -> None:
    ok, ax0, ay0, ax1, ay1 = clip_segment(x0, y0, x1, y1, _RECT)
    assert ok is accept
    if accept:
        assert (ax0, ay0, ax1, ay1) == pytest.approx((ex0, ey0, ex1, ey1))


def test_horizontal_line_crosses_left_boundary_in_output() -> None:
    svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <line x1="-20" y1="50" x2="80" y2="50" stroke="black"/>
</svg>"""
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
    )
    assert "M 0 50" in prepared.svg_text
    assert "L 80 50" in prepared.svg_text


def test_disconnected_paths_not_merged() -> None:
    svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <line x1="10" y1="10" x2="30" y2="10" stroke="black"/>
  <line x1="60" y1="80" x2="90" y2="80" stroke="black"/>
</svg>"""
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
    )
    assert prepared.path_count == 2
    assert prepared.svg_text.count(' d="M ') == 2


def test_long_cubic_flattens_without_hanging() -> None:
    """Regression: svgelements arc length can hang on extreme cubics (spiral bouquet paths)."""
    d = (
        "m 1377.69,861.44 c 37.2517,16.43671 45.6966,-5.84401 45.2487,-40.07687 "
        "12.6937,-86.54104 25.3875,-173.08209 38.0813,-259.62313"
    )
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 1123 794">
  <path d="{d}" fill="none" stroke="#111"/>
</svg>"""
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=420.0,
        viewport_height_mm=297.0,
        transform=ArtworkTransform.identity(),
    )
    assert prepared.path_count >= 1
    assert "<path" in prepared.svg_text


def _svg_line(x1: float, y1: float, x2: float, y2: float, *, page: float = 100.0) -> str:
    ns = "http://www.w3.org/2000/svg"
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="{ns}" width="{page}mm" height="{page}mm" '
        f'viewBox="0 0 {page} {page}">\n'
        f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black"/>\n'
        f"</svg>"
    )


def test_clip_inside_to_inside_keeps_segment() -> None:
    polylines = _prepare_polylines(_svg_line(10, 10, 40, 10))
    assert polylines == [[(10.0, 10.0), (40.0, 10.0)]]


def test_clip_inside_to_outside_truncates_at_boundary() -> None:
    polylines = _prepare_polylines(_svg_line(50, 50, 150, 50, page=200))
    assert polylines == [[(50.0, 50.0), (100.0, 50.0)]]


def test_clip_outside_to_inside_starts_at_boundary() -> None:
    polylines = _prepare_polylines(_svg_line(150, 50, 50, 50, page=200))
    assert polylines == [[(100.0, 50.0), (50.0, 50.0)]]


def test_clip_outside_to_outside_without_crossing_is_empty() -> None:
    with pytest.raises(Exception, match="No artwork intersects"):
        _prepare_polylines(_svg_line(110, 10, 120, 10, page=200))


def test_clip_outside_to_outside_crossing_keeps_visible_portion() -> None:
    polylines = _prepare_polylines(_svg_line(-10, 50, 110, 50))
    assert polylines == [[(0.0, 50.0), (100.0, 50.0)]]


_SQUARE_EXIT_REENTER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="200mm" '
    'viewBox="0 0 200 200">\n'
    '  <path d="M 50 50 L 150 50 L 150 150 L 50 150 Z" fill="none" stroke="black"/>\n'
    "</svg>"
)


def test_clip_exit_travel_outside_reenter_splits_polylines() -> None:
    polylines = _prepare_polylines(
        _SQUARE_EXIT_REENTER,
        viewport=(100.0, 100.0),
    )
    assert len(polylines) == 2
    assert polylines[0] == pytest.approx([(50.0, 50.0), (100.0, 50.0)], abs=_TOL)
    assert polylines[1] == pytest.approx([(50.0, 100.0), (50.0, 50.0)], abs=_TOL)
    _assert_no_diagonal_bridge(polylines, ((100.0, 50.0), (75.0, 100.0)))


def test_clip_scaled_rectangle_partially_outside() -> None:
    polylines = _prepare_polylines(
        _SQUARE_EXIT_REENTER.replace(
            "M 50 50 L 150 50 L 150 150 L 50 150 Z",
            "M 10 10 L 90 10 L 90 90 L 10 90 Z",
        ),
        transform=ArtworkTransform(scale=2.0),
    )
    assert len(polylines) == 2
    _assert_inside_viewport(polylines)


def test_clip_segment_on_viewport_boundary() -> None:
    polylines = _prepare_polylines(_svg_line(0, 50, 100, 50))
    assert polylines == [[(0.0, 50.0), (100.0, 50.0)]]


def test_clip_segment_touching_viewport_corner() -> None:
    polylines = _prepare_polylines(
        """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M 100 0 L 100 100" fill="none" stroke="black"/>
</svg>"""
    )
    assert len(polylines) == 1
    assert polylines[0][0][0] == pytest.approx(100.0, abs=_TOL)
    assert polylines[0][-1][1] == pytest.approx(100.0, abs=_TOL)


def test_closed_path_fully_inside_stays_one_polyline() -> None:
    polylines = _prepare_polylines(
        """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M 10 10 L 90 10 L 90 90 L 10 90 Z" fill="none" stroke="black"/>
</svg>"""
    )
    assert len(polylines) == 1
    assert len(polylines[0]) == 5
    assert polylines[0][0] == polylines[0][-1]


def test_b13_removes_consecutive_duplicate_points() -> None:
    polylines = _prepare_polylines(
        """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M 10 10 L 10 10 L 20 10" fill="none" stroke="black"/>
</svg>"""
    )
    assert polylines == [[(10.0, 10.0), (20.0, 10.0)]]


def test_b13_discards_zero_length_polyline() -> None:
    with pytest.raises(Exception, match="No artwork intersects"):
        _prepare_polylines(
            """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M 10 10 L 10 10" fill="none" stroke="black"/>
</svg>"""
        )


def test_empty_outside_viewport_raises() -> None:
    svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="50mm" height="50mm">
  <line x1="0" y1="0" x2="40" y2="0" stroke="black"/>
</svg>"""
    with pytest.raises(Exception, match="No artwork intersects"):
        prepare_positioned_plot_svg(
            svg,
            viewport_width_mm=100.0,
            viewport_height_mm=100.0,
            transform=ArtworkTransform(x_mm=200.0, y_mm=0.0, scale=1.0),
        )
