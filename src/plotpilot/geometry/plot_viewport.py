"""Transform artwork and clip vector geometry to the machine viewport."""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from svgelements import SVG, Arc, Close, Group, Line, Move, Shape

from plotpilot.geometry.liang_barsky import ClipRect, clip_segment
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.svg.page_geometry import SvgPageGeometry, parse_page_geometry
from plotpilot.svg.plot_dimensions import PlotDimensionError

CURVE_FLATNESS_MM = 0.05
COORD_TOLERANCE_MM = 0.01
# svgelements Shape.length() can hang on extreme cubics; cap flattening instead.
MAX_FLATTEN_STEPS_PER_SEGMENT = 512


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


@dataclass(frozen=True, slots=True)
class FlattenedDocumentGeometry:
    """Stroked subpaths flattened in physical document millimeters, before placement."""

    page_width_mm: float
    page_height_mm: float
    polylines: tuple[tuple[tuple[float, float], ...], ...]


def flatten_document_geometry(svg_text: str) -> FlattenedDocumentGeometry:
    """Parse and flatten stroked curves once, in document millimeters."""
    try:
        page = parse_page_geometry(svg_text)
    except PlotDimensionError as exc:
        raise PlotViewportError(exc.user_message) from exc

    svg_root = SVG.parse(io.StringIO(svg_text))
    to_mm = _SvgToMm.from_page(page, svg_root)
    subpaths = _flatten_document_subpaths(svg_root, to_mm)
    return FlattenedDocumentGeometry(
        page_width_mm=page.width_mm,
        page_height_mm=page.height_mm,
        polylines=tuple(tuple(points) for points in subpaths),
    )


def clip_document_polylines(
    polylines: tuple[tuple[tuple[float, float], ...], ...] | list[list[tuple[float, float]]],
    transform: ArtworkTransform,
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
    clip_x_min_mm: float = 0.0,
    clip_y_min_mm: float = 0.0,
    clip_x_max_mm: float | None = None,
    clip_y_max_mm: float | None = None,
) -> list[tuple[tuple[float, float], ...]]:
    """Place document polylines and clip them to an arbitrary machine rectangle.

    Omitted clip edges use the full viewport starting at (0, 0). Product callers
    pass the printable-area edges so margins do not shift machine coordinates.
    """
    transform.validate()
    clip = _resolve_clip_rect(
        viewport_width_mm,
        viewport_height_mm,
        clip_x_min_mm=clip_x_min_mm,
        clip_y_min_mm=clip_y_min_mm,
        clip_x_max_mm=clip_x_max_mm,
        clip_y_max_mm=clip_y_max_mm,
    )
    return _clip_document_subpaths(polylines, transform, clip)


def prepare_positioned_plot_svg(
    svg_text: str,
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
    transform: ArtworkTransform,
    clip_x_min_mm: float = 0.0,
    clip_y_min_mm: float = 0.0,
    clip_x_max_mm: float | None = None,
    clip_y_max_mm: float | None = None,
) -> PreparedPlotSvg:
    """Return clipped plot SVG in machine coordinates (1 unit = 1 mm)."""
    transform.validate()
    clip = _resolve_clip_rect(
        viewport_width_mm,
        viewport_height_mm,
        clip_x_min_mm=clip_x_min_mm,
        clip_y_min_mm=clip_y_min_mm,
        clip_x_max_mm=clip_x_max_mm,
        clip_y_max_mm=clip_y_max_mm,
    )
    flattened = flatten_document_geometry(svg_text)
    clipped_paths = _clip_document_subpaths(flattened.polylines, transform, clip)

    return emit_validated_plot_svg(
        clipped_paths,
        viewport_width_mm=viewport_width_mm,
        viewport_height_mm=viewport_height_mm,
        clip_x_min_mm=clip.x_min,
        clip_y_min_mm=clip.y_min,
        clip_x_max_mm=clip.x_max,
        clip_y_max_mm=clip.y_max,
    )


def emit_validated_plot_svg(
    clipped_paths: list[tuple[tuple[float, float], ...]] | list[list[tuple[float, float]]],
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
    clip_x_min_mm: float = 0.0,
    clip_y_min_mm: float = 0.0,
    clip_x_max_mm: float | None = None,
    clip_y_max_mm: float | None = None,
) -> PreparedPlotSvg:
    """Emit machine-space SVG and run the final geometry safety check.

    The SVG page stays the physical viewport. Coordinates must lie in *clip*.
    """
    if not clipped_paths:
        msg = "No artwork intersects the plot area."
        raise PlotViewportError(msg)

    clip = _resolve_clip_rect(
        viewport_width_mm,
        viewport_height_mm,
        clip_x_min_mm=clip_x_min_mm,
        clip_y_min_mm=clip_y_min_mm,
        clip_x_max_mm=clip_x_max_mm,
        clip_y_max_mm=clip_y_max_mm,
    )
    out_svg = _emit_svg(clipped_paths, viewport_width_mm, viewport_height_mm)
    _validate_emitted_svg(out_svg, viewport_width_mm, viewport_height_mm, clip)
    return PreparedPlotSvg(
        svg_text=out_svg,
        width_mm=viewport_width_mm,
        height_mm=viewport_height_mm,
        path_count=len(clipped_paths),
    )


def _resolve_clip_rect(
    viewport_width_mm: float,
    viewport_height_mm: float,
    *,
    clip_x_min_mm: float,
    clip_y_min_mm: float,
    clip_x_max_mm: float | None,
    clip_y_max_mm: float | None,
) -> ClipRect:
    if viewport_width_mm <= 0 or viewport_height_mm <= 0:
        msg = "Plot viewport size must be positive."
        raise PlotViewportError(msg)
    x_max = viewport_width_mm if clip_x_max_mm is None else clip_x_max_mm
    y_max = viewport_height_mm if clip_y_max_mm is None else clip_y_max_mm
    if x_max <= clip_x_min_mm or y_max <= clip_y_min_mm:
        msg = "Print margins leave no printable area."
        raise PlotViewportError(msg)
    return ClipRect(clip_x_min_mm, clip_y_min_mm, x_max, y_max)


def _validate_emitted_svg(
    svg_text: str,
    width_mm: float,
    height_mm: float,
    clip: ClipRect,
) -> None:
    """Keep the historical 3-argument validator call when the clip is the viewport."""
    full_viewport = (
        clip.x_min == 0.0
        and clip.y_min == 0.0
        and clip.x_max == width_mm
        and clip.y_max == height_mm
    )
    if full_viewport:
        _validate_output_geometry(svg_text, width_mm, height_mm)
        return
    _validate_output_geometry(
        svg_text,
        width_mm,
        height_mm,
        x_min_mm=clip.x_min,
        y_min_mm=clip.y_min,
        x_max_mm=clip.x_max,
        y_max_mm=clip.y_max,
    )


@dataclass(frozen=True, slots=True)
class _SvgToMm:
    """Map svgelements segment coordinates to physical millimeters."""

    page: SvgPageGeometry
    viewport_width_px: float
    viewport_height_px: float

    @classmethod
    def from_page(cls, page: SvgPageGeometry, root: SVG) -> _SvgToMm:
        return cls(
            page=page,
            viewport_width_px=float(root.width) if root.width else 0.0,
            viewport_height_px=float(root.height) if root.height else 0.0,
        )

    def point(self, x: float, y: float) -> tuple[float, float]:
        """Convert one svgelements segment coordinate pair to mm."""
        if self.page.viewbox is None:
            return self.page.user_point_to_mm(x, y)
        return self.page.viewport_pixel_to_mm(
            x,
            y,
            viewport_width_px=self.viewport_width_px,
            viewport_height_px=self.viewport_height_px,
        )


def _flatten_document_subpaths(
    svg: SVG,
    to_mm: _SvgToMm,
) -> list[list[tuple[float, float]]]:
    """Walk stroked geometry and return document-mm subpaths, unclipped."""
    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []

    def flush() -> None:
        nonlocal current
        if len(current) >= 2:
            subpaths.append(current)
        current = []

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
                    if not current:
                        current = [cursor_mm, subpath_start]
                    else:
                        current.append(subpath_start)
                flush()
                cursor_mm = subpath_start
                continue

            points = _segment_points_mm(segment, to_mm)
            if not points:
                continue
            if cursor_mm is None:
                cursor_mm = points[0]
            for px, py in points[1:]:
                point = (px, py)
                if not current:
                    current = [cursor_mm, point]
                else:
                    current.append(point)
                cursor_mm = point

        flush()

    return subpaths


def _clip_document_subpaths(
    polylines: tuple[tuple[tuple[float, float], ...], ...] | list[list[tuple[float, float]]],
    transform: ArtworkTransform,
    clip: ClipRect,
) -> list[tuple[tuple[float, float], ...]]:
    """Apply placement and Liang–Barsky clipping to pre-flattened document polylines."""
    transform.validate()
    origin_x = transform.x_mm
    origin_y = transform.y_mm
    scale = transform.scale
    output_paths: list[tuple[tuple[float, float], ...]] = []
    current: list[tuple[float, float]] = []

    def flush() -> None:
        nonlocal current
        sanitized = _sanitize_polyline(current)
        if sanitized is not None:
            output_paths.append(tuple(sanitized))
        current = []

    def plot_segment(x0_mm: float, y0_mm: float, x1_mm: float, y1_mm: float) -> None:
        nonlocal current
        ax0 = origin_x + x0_mm * scale
        ay0 = origin_y + y0_mm * scale
        ax1 = origin_x + x1_mm * scale
        ay1 = origin_y + y1_mm * scale
        ax0, ay0 = _snap_point_to_clip(ax0, ay0, clip)
        ax1, ay1 = _snap_point_to_clip(ax1, ay1, clip)
        accept, nx0, ny0, nx1, ny1 = clip_segment(ax0, ay0, ax1, ay1, clip)
        if not accept:
            flush()
            return
        if _points_near((nx0, ny0), (nx1, ny1)):
            return
        if not current:
            current = [(nx0, ny0), (nx1, ny1)]
        elif _points_near(current[-1], (nx0, ny0)):
            if not _points_near(current[-1], (nx1, ny1)):
                current.append((nx1, ny1))
        else:
            flush()
            current = [(nx0, ny0), (nx1, ny1)]

    for subpath in polylines:
        if len(subpath) < 2:
            continue
        previous = subpath[0]
        for point in subpath[1:]:
            plot_segment(previous[0], previous[1], point[0], point[1])
            previous = point
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


def _snap_point_to_clip(x: float, y: float, clip: ClipRect) -> tuple[float, float]:
    """Snap near-boundary float noise into the clip rectangle."""
    if abs(x - clip.x_min) <= COORD_TOLERANCE_MM:
        x = clip.x_min
    elif abs(x - clip.x_max) <= COORD_TOLERANCE_MM:
        x = clip.x_max
    if abs(y - clip.y_min) <= COORD_TOLERANCE_MM:
        y = clip.y_min
    elif abs(y - clip.y_max) <= COORD_TOLERANCE_MM:
        y = clip.y_max
    return x, y


def _points_near(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= COORD_TOLERANCE_MM and abs(a[1] - b[1]) <= COORD_TOLERANCE_MM


def _dedupe_consecutive_points(
    points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    if not points:
        return []
    deduped = [points[0]]
    for point in points[1:]:
        if not _points_near(deduped[-1], point):
            deduped.append(point)
    return deduped


def _sanitize_polyline(points: list[tuple[float, float]]) -> list[tuple[float, float]] | None:
    """Drop numerically degenerate polylines (B13)."""
    deduped = _dedupe_consecutive_points(points)
    if len(deduped) < 2:
        return None
    return deduped


def _estimate_segment_length_rendered(segment: object) -> float:
    """Conservative polyline length in svgelements segment coordinates."""
    if isinstance(segment, Line):
        return math.hypot(segment.end.x - segment.start.x, segment.end.y - segment.start.y)

    if isinstance(segment, Arc):
        try:
            arc_length = float(segment.length())
        except (ValueError, ZeroDivisionError, TypeError):
            arc_length = 0.0
        if arc_length > 0.0:
            return arc_length

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


def _emit_svg(
    paths: list[tuple[tuple[float, float], ...]] | list[list[tuple[float, float]]],
    width_mm: float,
    height_mm: float,
) -> str:
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


def _validate_output_geometry(
    svg_text: str,
    width_mm: float,
    height_mm: float,
    *,
    x_min_mm: float = 0.0,
    y_min_mm: float = 0.0,
    x_max_mm: float | None = None,
    y_max_mm: float | None = None,
) -> None:
    x_max = width_mm if x_max_mm is None else x_max_mm
    y_max = height_mm if y_max_mm is None else y_max_mm
    printable_is_machine = (
        x_min_mm == 0.0 and y_min_mm == 0.0 and x_max == width_mm and y_max == height_mm
    )
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        msg = "Plot preparation produced invalid SVG."
        raise PlotViewportError(msg) from exc

    tol = COORD_TOLERANCE_MM
    machine_message = (
        "Plot preparation produced geometry outside the machine work area. "
        "Plot cancelled for safety."
    )
    printable_message = (
        "Plot preparation produced geometry outside the printable area. Plot cancelled for safety."
    )
    for path in root.iter():
        if not path.tag.endswith("path"):
            continue
        d = path.get("d")
        if not d:
            continue
        for x, y in _parse_path_d_coords(d):
            if not math.isfinite(x) or not math.isfinite(y):
                raise PlotViewportError(machine_message)
            outside_machine = x < -tol or y < -tol or x > width_mm + tol or y > height_mm + tol
            outside_printable = (
                x < x_min_mm - tol or y < y_min_mm - tol or x > x_max + tol or y > y_max + tol
            )
            if outside_machine:
                raise PlotViewportError(machine_message)
            if outside_printable:
                message = machine_message if printable_is_machine else printable_message
                raise PlotViewportError(message)


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
