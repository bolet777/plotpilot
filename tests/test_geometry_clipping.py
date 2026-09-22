"""Liang–Barsky segment clipping and path splitting."""

from __future__ import annotations

import pytest

from plotpilot.geometry.liang_barsky import ClipRect, clip_segment
from plotpilot.geometry.plot_viewport import prepare_positioned_plot_svg
from plotpilot.models.artwork_transform import ArtworkTransform

_RECT = ClipRect(0.0, 0.0, 100.0, 100.0)


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
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">
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
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">
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
