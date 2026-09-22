"""Transform artwork and clip vector geometry to the machine viewport."""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from svgelements import SVG, Close, Group, Line, Move, Shape

from plotpilot.geometry.liang_barsky import ClipRect, clip_segment
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.svg.plot_dimensions import PlotDimensionError, parse_physical_size

CURVE_FLATNESS_MM = 0.05
COORD_TOLERANCE_MM = 0.01
# svgelements Shape.length() can hang on extreme cubics; cap flattening instead.
MAX_FLATTEN_STEPS_PER_SEGMENT = 512

_VIEWBOX_RE = re.compile(
    r"viewBox\s*=\s*[\"'](?P<values>[^\"']+)[\"']",
    re.IGNORECASE,
)
_NUMERIC_RE = re.compile(r"^[\s]*(-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")


class PlotViewportError(Exception):
    """Plot preparation failed for viewport/clipping reasons."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True, slots=True)
class PreparedPlotSvg:
    svg_text: str
    width_mm: float
    height_mm: float
    path_count: int


def prepare_positioned_plot_svg(
    svg_text: str,
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
    transform: ArtworkTransform,
) -> PreparedPlotSvg:
    """Return clipped plot SVG in machine coordinates (1 unit = 1 mm)."""
    transform.validate()
    if viewport_width_mm <= 0 or viewport_height_mm <= 0:
        msg = "Plot viewport size must be positive."
        raise PlotViewportError(msg)

    try:
        page = parse_physical_size(svg_text)
    except PlotDimensionError as exc:
        raise PlotViewportError(exc.user_message) from exc

    svg_root = SVG.parse(io.StringIO(svg_text))
    viewbox = _read_viewbox_user(svg_text, page.width_mm, page.height_mm)
    to_mm = _SvgToMm.from_root(page.width_mm, page.height_mm, viewbox, svg_root)

    clip = ClipRect(0.0, 0.0, viewport_width_mm, viewport_height_mm)
    clipped_paths = _clip_svg_geometry(
        svg_root,
        to_mm,
        transform,
        clip,
    )

    if not clipped_paths:
        msg = "No artwork intersects the plot area."
        raise PlotViewportError(msg)

    out_svg = _emit_svg(clipped_paths, viewport_width_mm, viewport_height_mm)
    _validate_output_geometry(out_svg, viewport_width_mm, viewport_height_mm)

    return PreparedPlotSvg(
        svg_text=out_svg,
        width_mm=viewport_width_mm,
        height_mm=viewport_height_mm,
        path_count=len(clipped_paths),
    )


@dataclass(frozen=True, slots=True)
class _SvgToMm:
    """Map svgelements segment coordinates to physical millimeters."""

    width_mm: float
    height_mm: float
    viewbox: tuple[float, float, float, float]
    viewport_width_px: float
    viewport_height_px: float
    coordinates_in_viewport_pixels: bool

    @classmethod
    def from_root(
        cls,
        width_mm: float,
        height_mm: float,
        viewbox: tuple[float, float, float, float],
        root: SVG,
    ) -> _SvgToMm:
        return cls(
            width_mm=width_mm,
            height_mm=height_mm,
            viewbox=viewbox,
            viewport_width_px=float(root.width) if root.width else 0.0,
            viewport_height_px=float(root.height) if root.height else 0.0,
            coordinates_in_viewport_pixels=_coordinates_are_viewport_pixels(root, viewbox),
        )

    def point(self, x: float, y: float) -> tuple[float, float]:
        """Convert one svgelements segment coordinate pair to mm."""
        vx, vy, vw, vh = self.viewbox
        if (
            self.coordinates_in_viewport_pixels
            and self.viewport_width_px > 0
            and self.viewport_height_px > 0
            and vw > 0
            and vh > 0
        ):
            # segments(transformed=True) are in root viewport pixels for viewBox SVGs and
            # for some viewBox-less exports (e.g. DrawingBot) where coords exceed user width.
            ux = vx + (x / self.viewport_width_px) * vw
            uy = vy + (y / self.viewport_height_px) * vh
        else:
            ux, uy = x, y
        if vw <= 0 or vh <= 0:
            return ux, uy
        return (ux - vx) * self.width_mm / vw, (uy - vy) * self.height_mm / vh


def _coordinates_are_viewport_pixels(
    root: SVG,
    viewbox: tuple[float, float, float, float],
) -> bool:
    if root.viewbox is not None:
        return True
    _vx, _vy, vw, vh = viewbox
    if vw <= 0 or vh <= 0:
        return False
    max_abs = _max_transformed_coordinate(root)
    return max_abs > max(vw, vh) * 1.01


def _max_transformed_coordinate(root: SVG) -> float:
    max_abs = 0.0
    for element in root.elements():
        if isinstance(element, (SVG, Group)) or not isinstance(element, Shape):
            continue
        for segment in element.segments(transformed=True):
            for point in (getattr(segment, "start", None), getattr(segment, "end", None)):
                if point is None or not hasattr(point, "x"):
                    continue
                max_abs = max(max_abs, abs(point.x), abs(point.y))
    return max_abs


def _read_viewbox_user(
    svg_text: str,
    width_mm: float,
    height_mm: float,
) -> tuple[float, float, float, float]:
    match = _VIEWBOX_RE.search(svg_text)
    if match:
        parts = match.group("values").replace(",", " ").split()
        if len(parts) == 4:
            return tuple(float(p) for p in parts)  # type: ignore[return-value]

    root_match = re.search(r"<svg[^>]+width\s*=\s*[\"']([^\"']+)", svg_text, re.I)
    height_match = re.search(r"<svg[^>]+height\s*=\s*[\"']([^\"']+)", svg_text, re.I)
    user_w = _numeric_length(root_match.group(1) if root_match else str(width_mm))
    user_h = _numeric_length(height_match.group(1) if height_match else str(height_mm))
    if user_w <= 0 or user_h <= 0:
        return 0.0, 0.0, width_mm, height_mm
    return 0.0, 0.0, user_w, user_h


def _numeric_length(raw: str) -> float:
    match = _NUMERIC_RE.match(raw.strip())
    if not match:
        return 0.0
    return float(match.group(1))


def _clip_svg_geometry(
    svg: SVG,
    to_mm: _SvgToMm,
    transform: ArtworkTransform,
    clip: ClipRect,
) -> list[list[tuple[float, float]]]:
    output_paths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    pen_xy: tuple[float, float] | None = None

    def flush() -> None:
        nonlocal current, pen_xy
        if len(current) >= 2:
            output_paths.append(current)
        current = []
        pen_xy = None

    def plot_segment(x0_mm: float, y0_mm: float, x1_mm: float, y1_mm: float) -> None:
        nonlocal current, pen_xy
        ax0, ay0 = transform.apply_point(x0_mm, y0_mm)
        ax1, ay1 = transform.apply_point(x1_mm, y1_mm)
        if pen_xy is not None:
            sx, sy = pen_xy
            if (sx, sy) != (ax0, ay0):
                ax0, ay0 = sx, sy
        accept, nx0, ny0, nx1, ny1 = clip_segment(ax0, ay0, ax1, ay1, clip)
        if not accept:
            flush()
            return
        if pen_xy is None or not current:
            current = [(nx0, ny0), (nx1, ny1)]
        elif (nx0, ny0) != current[-1]:
            flush()
            current = [(nx0, ny0), (nx1, ny1)]
        elif (nx1, ny1) != current[-1]:
            current.append((nx1, ny1))
        pen_xy = (nx1, ny1)

    for element in svg.elements():
        if isinstance(element, (SVG, Group)):
            continue
        if not isinstance(element, Shape):
            continue
        if not _element_has_stroke(element):
            continue

        subpath_start: tuple[float, float] | None = None
        cursor_mm: tuple[float, float] | None = None

        for segment in element.segments(transformed=True):
            if isinstance(segment, Move):
                flush()
                cursor_mm = to_mm.point(segment.end.x, segment.end.y)
                subpath_start = cursor_mm
                continue

            if isinstance(segment, Close):
                if cursor_mm is not None and subpath_start is not None:
                    plot_segment(cursor_mm[0], cursor_mm[1], subpath_start[0], subpath_start[1])
                flush()
                cursor_mm = subpath_start
                continue

            points = _segment_points_mm(segment, to_mm)
            if not points:
                continue
            if cursor_mm is None:
                cursor_mm = points[0]
            for px, py in points[1:]:
                plot_segment(cursor_mm[0], cursor_mm[1], px, py)
                cursor_mm = (px, py)

        flush()

    return output_paths


def _element_has_stroke(element: Shape) -> bool:
    stroke = getattr(element, "stroke", None)
    if stroke is None:
        return False
    value = str(stroke.value).lower() if hasattr(stroke, "value") else str(stroke).lower()
    return value not in {"none", "transparent"}


def _segment_points_mm(segment: object, to_mm: _SvgToMm) -> list[tuple[float, float]]:
    if isinstance(segment, Line):
        return [
            to_mm.point(segment.start.x, segment.start.y),
            to_mm.point(segment.end.x, segment.end.y),
        ]

    flatness_rendered = _flatness_rendered_units(to_mm, CURVE_FLATNESS_MM)
    length = _estimate_segment_length_rendered(segment)
    if length <= 0:
        pt = segment.end  # type: ignore[attr-defined]
        return [to_mm.point(pt.x, pt.y)]

    steps = max(2, int(math.ceil(length / flatness_rendered)))
    steps = min(steps, MAX_FLATTEN_STEPS_PER_SEGMENT)
    points: list[tuple[float, float]] = []
    for i in range(steps + 1):
        t = i / steps
        pt = segment.point(t)  # type: ignore[attr-defined]
        points.append(to_mm.point(pt.x, pt.y))
    return points


def _estimate_segment_length_rendered(segment: object) -> float:
    """Conservative polyline length in svgelements segment coordinates."""
    if isinstance(segment, Line):
        return math.hypot(segment.end.x - segment.start.x, segment.end.y - segment.start.y)

    start = segment.start  # type: ignore[attr-defined]
    end = segment.end  # type: ignore[attr-defined]
    chain = [start]
    for name in ("control1", "control2"):
        control = getattr(segment, name, None)
        if control is not None:
            chain.append(control)
    chain.append(end)

    total = 0.0
    for a, b in zip(chain, chain[1:], strict=False):
        total += math.hypot(b.x - a.x, b.y - a.y)
    return total


def _flatness_rendered_units(to_mm: _SvgToMm, flatness_mm: float) -> float:
    origin = to_mm.point(0.0, 0.0)
    unit_x = to_mm.point(1.0, 0.0)
    unit_y = to_mm.point(0.0, 1.0)
    mm_per_x = abs(unit_x[0] - origin[0])
    mm_per_y = abs(unit_y[1] - origin[1])
    scales = [value for value in (mm_per_x, mm_per_y) if value > 0]
    if not scales:
        return flatness_mm
    mm_per_rendered = min(scales)
    return flatness_mm / mm_per_rendered


def _emit_svg(paths: list[list[tuple[float, float]]], width_mm: float, height_mm: float) -> str:
    path_tags: list[str] = []
    for subpath in paths:
        if len(subpath) < 2:
            continue
        parts = [f"M {_fmt(subpath[0][0])} {_fmt(subpath[0][1])}"]
        for x, y in subpath[1:]:
            parts.append(f"L {_fmt(x)} {_fmt(y)}")
        path_tags.append(
            f'  <path d="{" ".join(parts)}" fill="none" stroke="#000000" stroke-width="0.2"/>'
        )

    body = "\n".join(path_tags)
    w = _fmt(width_mm)
    h = _fmt(height_mm)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
        f'viewBox="0 0 {w} {h}">\n'
        f"{body}\n"
        "</svg>\n"
    )


def _fmt(value: float) -> str:
    if abs(value) < 1e-9:
        return "0"
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _validate_output_geometry(svg_text: str, width_mm: float, height_mm: float) -> None:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        msg = "Plot preparation produced invalid SVG."
        raise PlotViewportError(msg) from exc

    tol = COORD_TOLERANCE_MM
    for path in root.iter():
        if not path.tag.endswith("path"):
            continue
        d = path.get("d")
        if not d:
            continue
        for x, y in _parse_path_d_coords(d):
            if not math.isfinite(x) or not math.isfinite(y):
                msg = (
                    "Plot preparation produced geometry outside the machine work area. "
                    "Plot cancelled for safety."
                )
                raise PlotViewportError(msg)
            if x < -tol or y < -tol or x > width_mm + tol or y > height_mm + tol:
                msg = (
                    "Plot preparation produced geometry outside the machine work area. "
                    "Plot cancelled for safety."
                )
                raise PlotViewportError(msg)


def _parse_path_d_coords(d: str) -> list[tuple[float, float]]:
    tokens = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?|[a-zA-Z]", d)
    coords: list[tuple[float, float]] = []
    i = 0
    cmd = ""
    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            cmd = token
            i += 1
            continue
        if cmd in {"M", "L"}:
            if i + 1 >= len(tokens):
                break
            x = float(tokens[i])
            y = float(tokens[i + 1])
            coords.append((x, y))
            i += 2
        else:
            i += 1
    return coords
