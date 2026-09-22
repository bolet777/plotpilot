"""Positioned plot preparation service."""

from __future__ import annotations

from plotpilot.geometry.plot_viewport import PlotViewportError
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg


def test_output_svg_uses_machine_viewport_dimensions() -> None:
    layer_svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="100mm">
  <line x1="10" y1="10" x2="190" y2="10" stroke="black"/>
</svg>"""
    prepared = prepare_layer_plot_svg(
        layer_svg,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform.identity(),
    )
    assert 'width="' in prepared.svg_text
    assert "mm" in prepared.svg_text
    assert prepared.width_mm > 0


def test_transform_negative_x_still_produces_clipped_segment() -> None:
    layer_svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">
  <line x1="0" y1="50" x2="100" y2="50" stroke="black"/>
</svg>"""
    prepared = prepare_layer_plot_svg(
        layer_svg,
        plot_settings=PlotSettings(model=1),
        transform=ArtworkTransform(x_mm=-25.0, y_mm=0.0, scale=1.0),
    )
    assert prepared.path_count >= 1


def test_empty_intersection_raises() -> None:
    layer_svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm">
  <line x1="0" y1="0" x2="20" y2="0" stroke="black"/>
</svg>"""
    try:
        prepare_layer_plot_svg(
            layer_svg,
            plot_settings=PlotSettings(model=1),
            transform=ArtworkTransform(x_mm=500.0, y_mm=0.0, scale=1.0),
        )
    except PlotViewportError as exc:
        assert "No artwork intersects" in exc.user_message
    else:
        raise AssertionError("expected PlotViewportError")
