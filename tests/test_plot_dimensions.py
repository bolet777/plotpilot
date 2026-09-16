"""SVG dimension validation for plotting."""

from __future__ import annotations

import pytest

from plotpilot.svg.plot_dimensions import PlotDimensionError, validate_plot_svg_dimensions


def test_accepts_mm_units() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm"></svg>'
    w, h = validate_plot_svg_dimensions(svg)
    assert w == pytest.approx(100.0)
    assert h == pytest.approx(50.0)


def test_accepts_unitless_as_px() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>'
    w, h = validate_plot_svg_dimensions(svg)
    assert w > 0 and h > 0


def test_rejects_missing_height() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100mm"></svg>'
    with pytest.raises(PlotDimensionError):
        validate_plot_svg_dimensions(svg)


def test_rejects_percent_dimensions() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="50mm"></svg>'
    with pytest.raises(PlotDimensionError):
        validate_plot_svg_dimensions(svg)
