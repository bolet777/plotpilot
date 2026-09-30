"""Prototype: SVG → vpype read → mm normalization → ArtworkTransform → clip.

This module is evaluation-only. It does not replace ``plot_viewport`` or touch the UI.
"""

from __future__ import annotations

import io
from enum import StrEnum
from typing import TYPE_CHECKING

import numpy as np
import svgelements
import vpype
from vpype.model import as_vector

from plotpilot.geometry.liang_barsky import ClipRect, clip_segment
from plotpilot.geometry.plot_viewport import COORD_TOLERANCE_MM, CURVE_FLATNESS_MM
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.svg.page_geometry import SvgPageGeometry, parse_page_geometry

if TYPE_CHECKING:
    from golden_oracle import GoldenObservation

PX_PER_MM = 96.0 / 25.4


class VpypePrepareError(Exception):
    """Vpype spike could not produce geometry."""


class ClipBackend(StrEnum):
    """Which clipper to apply after mm normalization."""

    LIANG_BARSKY = "liang_barsky"
    VPYPE_RECT = "vpype_rect"


def prepare_vpype_polylines_mm(
    svg_text: str,
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
    transform: ArtworkTransform,
    clip_backend: ClipBackend = ClipBackend.LIANG_BARSKY,
) -> list[list[tuple[float, float]]]:
    """Return machine-space polylines comparable to ``prepare_positioned_plot_svg`` output."""
    transform.validate()
    if viewport_width_mm <= 0 or viewport_height_mm <= 0:
        msg = "Plot viewport size must be positive."
        raise VpypePrepareError(msg)

    quantization_px = CURVE_FLATNESS_MM * PX_PER_MM
    try:
        lc, _width, _height = vpype.read_svg(
            io.StringIO(svg_text),
            quantization=quantization_px,
            crop=False,
        )
    except Exception as exc:
        raise VpypePrepareError(str(exc)) from exc

    if lc.is_empty():
        msg = "No artwork intersects the plot area."
        raise VpypePrepareError(msg)

    page = parse_page_geometry(svg_text)
    root = svgelements.SVG.parse(io.StringIO(svg_text))
    polylines_mm = _line_collection_to_mm(lc, page, root)

    transformed = _apply_transform(polylines_mm, transform)
    if clip_backend is ClipBackend.LIANG_BARSKY:
        clipped = _clip_liang_barsky(
            transformed,
            viewport_width_mm=viewport_width_mm,
            viewport_height_mm=viewport_height_mm,
        )
    else:
        clipped = _clip_vpype_rect(
            transformed,
            viewport_width_mm=viewport_width_mm,
            viewport_height_mm=viewport_height_mm,
        )

    if not clipped:
        msg = "No artwork intersects the plot area."
        raise VpypePrepareError(msg)
    return clipped


def observe_vpype_golden(
    case: str,
    preparation_id: str = "document",
    *,
    clip_backend: ClipBackend = ClipBackend.LIANG_BARSKY,
) -> GoldenObservation:
    """Run one golden preparation through the vpype spike (mirrors ``observe_golden``)."""
    from golden_oracle import (
        GoldenObservation,
        _preparation_by_id,
        _source_svg,
        _transform,
        load_expectation,
    )

    expectation = load_expectation(case)
    preparation = _preparation_by_id(expectation, preparation_id)
    svg_text = _source_svg(case, expectation, preparation)
    viewport = expectation["viewport_mm"]
    transform = _transform(expectation)
    try:
        polylines = prepare_vpype_polylines_mm(
            svg_text,
            viewport_width_mm=float(viewport[0]),
            viewport_height_mm=float(viewport[1]),
            transform=transform,
            clip_backend=clip_backend,
        )
    except VpypePrepareError as exc:
        return GoldenObservation(polylines_mm=None, error=str(exc))
    return GoldenObservation(polylines_mm=polylines, error=None)


def _line_collection_to_mm(
    lc: vpype.LineCollection,
    page: SvgPageGeometry,
    root: svgelements.SVG,
) -> list[list[tuple[float, float]]]:
    viewport_width_px = float(root.width) if root.width else 0.0
    viewport_height_px = float(root.height) if root.height else 0.0
    polylines: list[list[tuple[float, float]]] = []
    for line in lc:
        points = as_vector(line)
        converted: list[tuple[float, float]] = []
        for x, y in points:
            converted.append(
                _user_point_to_mm(
                    float(x),
                    float(y),
                    page,
                    viewport_width_px=viewport_width_px,
                    viewport_height_px=viewport_height_px,
                )
            )
        if len(converted) >= 2:
            polylines.append(converted)
    return polylines


def _user_point_to_mm(
    x: float,
    y: float,
    page: SvgPageGeometry,
    *,
    viewport_width_px: float,
    viewport_height_px: float,
) -> tuple[float, float]:
    if page.viewbox is None:
        return x / PX_PER_MM, y / PX_PER_MM
    vx, vy, vbw, vbh = page.viewbox
    if viewport_width_px <= 0 or viewport_height_px <= 0 or vbw <= 0 or vbh <= 0:
        return page.user_point_to_mm(x, y)
    ux = vx + (x / viewport_width_px) * vbw
    uy = vy + (y / viewport_height_px) * vbh
    return page.user_point_to_mm(ux, uy)


def _apply_transform(
    polylines: list[list[tuple[float, float]]],
    transform: ArtworkTransform,
) -> list[list[tuple[float, float]]]:
    out: list[list[tuple[float, float]]] = []
    for polyline in polylines:
        out.append([transform.apply_point(x, y) for x, y in polyline])
    return out


def _clip_liang_barsky(
    polylines: list[list[tuple[float, float]]],
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
) -> list[list[tuple[float, float]]]:
    clip = ClipRect(0.0, 0.0, viewport_width_mm, viewport_height_mm)
    output: list[list[tuple[float, float]]] = []
    for polyline in polylines:
        current: list[tuple[float, float]] = []
        for index in range(len(polyline) - 1):
            x0, y0 = polyline[index]
            x1, y1 = polyline[index + 1]
            accept, nx0, ny0, nx1, ny1 = clip_segment(x0, y0, x1, y1, clip)
            if not accept:
                if len(current) >= 2:
                    output.append(current)
                current = []
                continue
            if not current:
                current = [(nx0, ny0), (nx1, ny1)]
            elif _points_near(current[-1], (nx0, ny0)):
                if not _points_near(current[-1], (nx1, ny1)):
                    current.append((nx1, ny1))
            else:
                if len(current) >= 2:
                    output.append(current)
                current = [(nx0, ny0), (nx1, ny1)]
        if len(current) >= 2:
            output.append(current)
    return output


def _clip_vpype_rect(
    polylines: list[list[tuple[float, float]]],
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
) -> list[list[tuple[float, float]]]:
    lc = vpype.LineCollection()
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        arr = np.array([complex(x, y) for x, y in polyline])
        lc.append(arr)
    lc.crop(0.0, 0.0, viewport_width_mm, viewport_height_mm)
    return _complex_lines_to_polylines(lc)


def _complex_lines_to_polylines(lc: vpype.LineCollection) -> list[list[tuple[float, float]]]:
    out: list[list[tuple[float, float]]] = []
    for line in lc:
        points = as_vector(line)
        polyline = [(float(x), float(y)) for x, y in points]
        if len(polyline) >= 2:
            out.append(polyline)
    return out


def _points_near(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= COORD_TOLERANCE_MM and abs(a[1] - b[1]) <= COORD_TOLERANCE_MM
