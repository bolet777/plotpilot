"""Validate physical SVG page size before sending to AxiDraw."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from plotpilot.svg.parse import is_svg_root

_LENGTH_RE = re.compile(
    r"^\s*(?P<value>-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(?P<unit>[a-zA-Z%]*)\s*$"
)

# SVG/CSS absolute units → millimeters (px at 96 dpi).
_UNIT_TO_MM: dict[str, float] = {
    "": 25.4 / 96.0,
    "px": 25.4 / 96.0,
    "pt": 25.4 / 72.0,
    "pc": 25.4 / 6.0,
    "mm": 1.0,
    "cm": 10.0,
    "in": 25.4,
}


class PlotDimensionError(Exception):
    """Plotting refused because page size is missing or ambiguous."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


def validate_plot_svg_dimensions(svg_text: str) -> tuple[float, float]:
    """Return (width_mm, height_mm) or raise PlotDimensionError."""
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise PlotDimensionError("Could not read SVG for plotting.") from exc

    if not is_svg_root(root):
        raise PlotDimensionError("Not a valid SVG document for plotting.")

    width_raw = root.get("width")
    height_raw = root.get("height")
    if not width_raw or not height_raw:
        raise PlotDimensionError(
            "SVG must have both width and height attributes with physical units "
            "(for example mm, cm, in, or px) before plotting."
        )

    width_mm = _parse_length_mm(width_raw)
    height_mm = _parse_length_mm(height_raw)
    if width_mm <= 0 or height_mm <= 0:
        raise PlotDimensionError("SVG width and height must be positive.")

    return width_mm, height_mm


def _parse_length_mm(raw: str) -> float:
    match = _LENGTH_RE.match(raw)
    if not match:
        raise PlotDimensionError(f"Could not parse SVG dimension: {raw!r}")

    value = float(match.group("value"))
    unit = match.group("unit").lower()
    if unit in {"%", "em", "ex", "rem"}:
        raise PlotDimensionError(f"Relative SVG dimension {raw!r} is not supported for plotting.")
    if unit not in _UNIT_TO_MM:
        raise PlotDimensionError(f"Unsupported SVG dimension unit in {raw!r}.")

    return value * _UNIT_TO_MM[unit]
