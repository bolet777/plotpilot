"""Canonical SVG root page geometry (user space → physical mm)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from plotpilot.svg.parse import is_svg_root, parse_svg_text
from plotpilot.svg.plot_dimensions import PlotDimensionError, parse_physical_size

# SVG/CSS px at 96 dpi — user units when the root has no viewBox.
CSS_PX_TO_MM = 25.4 / 96.0

_VIEWBOX_SPLIT_RE = re.compile(r"[\s,]+")


@dataclass(frozen=True, slots=True)
class SvgPageGeometry:
    """Physical page size and root viewBox semantics for coordinate mapping."""

    width_mm: float
    height_mm: float
    viewbox: tuple[float, float, float, float] | None
    preserve_aspect_ratio: str | None

    def user_point_to_mm(self, x: float, y: float) -> tuple[float, float]:
        """Map a point in SVG user space to millimeters on the physical page."""
        if self.viewbox is None:
            return x * CSS_PX_TO_MM, y * CSS_PX_TO_MM
        vx, vy, vw, vh = self.viewbox
        if vw <= 0 or vh <= 0:
            return x, y
        return (x - vx) * self.width_mm / vw, (y - vy) * self.height_mm / vh

    def viewport_pixel_to_mm(
        self,
        x: float,
        y: float,
        *,
        viewport_width_px: float,
        viewport_height_px: float,
    ) -> tuple[float, float]:
        """Map svgelements viewport-pixel coords to mm (root viewBox present)."""
        if self.viewbox is None:
            msg = "viewport_pixel_to_mm requires a root viewBox"
            raise ValueError(msg)
        vx, vy, vw, vh = self.viewbox
        if viewport_width_px <= 0 or viewport_height_px <= 0 or vw <= 0 or vh <= 0:
            return self.user_point_to_mm(x, y)
        ux = vx + (x / viewport_width_px) * vw
        uy = vy + (y / viewport_height_px) * vh
        return self.user_point_to_mm(ux, uy)


def parse_page_geometry(svg_text: str) -> SvgPageGeometry:
    """Parse authoritative page geometry from the root ``<svg>`` element."""
    root = parse_svg_text(svg_text)
    physical = parse_physical_size(svg_text)
    return page_geometry_from_root(root, physical.width_mm, physical.height_mm)


def page_geometry_from_root(
    root: Element,
    width_mm: float,
    height_mm: float,
) -> SvgPageGeometry:
    """Build geometry from root attributes and known physical page size."""
    if not is_svg_root(root):
        raise PlotDimensionError("Not a valid SVG document for plotting.")

    viewbox = _parse_viewbox_attribute(
        root.get("viewBox") or root.get("viewbox"),
    )
    preserve = root.get("preserveAspectRatio") or root.get("preserveaspectratio")

    return SvgPageGeometry(
        width_mm=width_mm,
        height_mm=height_mm,
        viewbox=viewbox,
        preserve_aspect_ratio=preserve,
    )


def _parse_viewbox_attribute(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw or not raw.strip():
        return None
    parts = _VIEWBOX_SPLIT_RE.split(raw.strip())
    if len(parts) != 4:
        return None
    try:
        values = tuple(float(part) for part in parts)
    except ValueError:
        return None
    return values  # type: ignore[return-value]
