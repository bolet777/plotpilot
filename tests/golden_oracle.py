"""Compare prepared plot SVG against hand-calculated millimeter expectations.

The oracle parses PlotPilot's emitted ``M``/``L`` paths. It does not call the
clipper, flattener, or unit heuristic under test.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from plotpilot.geometry.plot_viewport import PlotViewportError, prepare_positioned_plot_svg
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plot_service import plot_svg_for_layer
from plotpilot.services.svg_loader import load_svg_from_path

GOLDEN_ROOT = Path(__file__).resolve().parent / "fixtures" / "golden"
_DEFAULT_TOLERANCE_MM = 0.02
_TOKEN_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?|[A-Za-z]")


@dataclass(frozen=True, slots=True)
class GoldenObservation:
    """Prepared polylines, or the preparation error string."""

    polylines_mm: list[list[tuple[float, float]]] | None
    error: str | None


def assert_golden(case: str, *, only: str | None = None) -> None:
    """Prepare *case* and compare it with ``<case>.expected.json``."""
    expectation = load_expectation(case)
    if expectation.get("policy") == "pending":
        msg = f"{case}: policy is pending; do not assert plotted geometry"
        raise AssertionError(msg)

    failures: list[str] = []
    for preparation in _selected_preparations(expectation, only):
        try:
            _assert_preparation(case, expectation, preparation)
        except AssertionError as exc:
            failures.append(str(exc))
    if failures:
        raise AssertionError("\n\n".join(failures))


def observe_golden(case: str, preparation_id: str = "document") -> GoldenObservation:
    """Run one preparation and return polylines or the error. No comparison."""
    expectation = load_expectation(case)
    preparation = _preparation_by_id(expectation, preparation_id)
    try:
        svg_text = _source_svg(case, expectation, preparation)
        prepared = prepare_positioned_plot_svg(
            svg_text,
            viewport_width_mm=float(expectation["viewport_mm"][0]),
            viewport_height_mm=float(expectation["viewport_mm"][1]),
            transform=_transform(expectation),
        )
    except PlotViewportError as exc:
        return GoldenObservation(polylines_mm=None, error=exc.user_message)
    return GoldenObservation(
        polylines_mm=parse_prepared_polylines(prepared.svg_text),
        error=None,
    )


def load_expectation(case: str) -> dict:
    path = _expected_path(case)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"{case}: expected JSON must be an object"
        raise AssertionError(msg)
    return data


def parse_prepared_polylines(svg_text: str) -> list[list[tuple[float, float]]]:
    """Read machine-space polylines from prepared SVG (``M``/``L`` only)."""
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        msg = f"Prepared SVG is not XML: {exc}"
        raise AssertionError(msg) from exc

    polylines: list[list[tuple[float, float]]] = []
    for element in root.iter():
        if not str(element.tag).endswith("path"):
            continue
        path_data = element.get("d")
        if not path_data:
            continue
        polylines.append(_parse_move_line_path(path_data))
    return polylines


def polyline_bbox(
    polylines: list[list[tuple[float, float]]],
) -> tuple[float, float, float, float]:
    points = [point for polyline in polylines for point in polyline]
    if not points:
        msg = "No polyline points to bound"
        raise AssertionError(msg)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _assert_preparation(case: str, expectation: dict, preparation: dict) -> None:
    label = f"{case} [{preparation['id']}]"
    tolerance = float(expectation.get("tolerance_mm", _DEFAULT_TOLERANCE_MM))
    observation = _prepare(case, expectation, preparation)
    if observation.error is not None:
        msg = (
            f"{label}: preparation failed: {observation.error}\n"
            f"expected {_expectation_summary(expectation)}"
        )
        raise AssertionError(msg)

    assert observation.polylines_mm is not None
    actual = observation.polylines_mm
    if "polylines_mm" in expectation:
        _assert_polylines(label, actual, expectation["polylines_mm"], tolerance)
    if "bbox_mm" in expectation:
        _assert_bbox(label, polyline_bbox(actual), expectation["bbox_mm"], tolerance)
    if "min_points" in expectation:
        count = sum(len(polyline) for polyline in actual)
        minimum = int(expectation["min_points"])
        if count < minimum:
            msg = (
                f"{label}: expected at least {minimum} points, got {count}\nactual={_dump(actual)}"
            )
            raise AssertionError(msg)
    if "circle_mm" in expectation:
        _assert_circle(
            label,
            actual,
            expectation["circle_mm"],
            viewport=expectation["viewport_mm"],
        )


def _prepare(case: str, expectation: dict, preparation: dict) -> GoldenObservation:
    try:
        svg_text = _source_svg(case, expectation, preparation)
        prepared = prepare_positioned_plot_svg(
            svg_text,
            viewport_width_mm=float(expectation["viewport_mm"][0]),
            viewport_height_mm=float(expectation["viewport_mm"][1]),
            transform=_transform(expectation),
        )
    except PlotViewportError as exc:
        return GoldenObservation(polylines_mm=None, error=exc.user_message)
    return GoldenObservation(
        polylines_mm=parse_prepared_polylines(prepared.svg_text),
        error=None,
    )


def _source_svg(case: str, expectation: dict, preparation: dict) -> str:
    svg_path = _svg_path(case, expectation)
    mode = preparation.get("mode", "document")
    if mode == "document":
        return svg_path.read_text(encoding="utf-8")
    if mode != "isolated_layer":
        msg = f"{case}: unknown preparation mode {mode!r}"
        raise AssertionError(msg)

    document = load_svg_from_path(svg_path)
    layer_name = preparation.get("layer_name")
    matches = [layer for layer in layers_for_document(document) if layer.name == layer_name]
    if len(matches) != 1:
        found = [layer.name for layer in layers_for_document(document)]
        msg = f"{case}: expected one layer named {layer_name!r}, found {found}"
        raise AssertionError(msg)
    return plot_svg_for_layer(document, matches[0])


def _svg_path(case: str, expectation: dict) -> Path:
    override = expectation.get("svg")
    if override:
        return _expected_path(case).parent / str(override)
    return GOLDEN_ROOT / f"{case}.svg"


def _expected_path(case: str) -> Path:
    return GOLDEN_ROOT / f"{case}.expected.json"


def _selected_preparations(expectation: dict, only: str | None) -> list[dict]:
    preparations = list(expectation.get("preparations") or [{"id": "document", "mode": "document"}])
    if only is None:
        return preparations
    return [_preparation_by_id(expectation, only)]


def _preparation_by_id(expectation: dict, preparation_id: str) -> dict:
    preparations = list(expectation.get("preparations") or [{"id": "document", "mode": "document"}])
    matches = [item for item in preparations if item.get("id") == preparation_id]
    if len(matches) != 1:
        found = [item.get("id") for item in preparations]
        msg = f"expected one preparation id {preparation_id!r}, found {found}"
        raise AssertionError(msg)
    return matches[0]


def _transform(expectation: dict) -> ArtworkTransform:
    raw = expectation.get("transform") or {}
    return ArtworkTransform(
        x_mm=float(raw.get("x_mm", 0.0)),
        y_mm=float(raw.get("y_mm", 0.0)),
        scale=float(raw.get("scale", 1.0)),
    )


def _assert_polylines(
    label: str,
    actual: list[list[tuple[float, float]]],
    expected: list,
    tolerance: float,
) -> None:
    if len(actual) != len(expected):
        msg = (
            f"{label}: expected {len(expected)} polylines, got {len(actual)}\n"
            f"expected={_dump(expected)}\nactual={_dump(actual)}"
        )
        raise AssertionError(msg)
    for index, (actual_line, expected_line) in enumerate(zip(actual, expected, strict=True)):
        if len(actual_line) != len(expected_line):
            msg = (
                f"{label}: polyline {index} expected {len(expected_line)} points, "
                f"got {len(actual_line)}\n"
                f"expected={expected_line}\nactual={actual_line}"
            )
            raise AssertionError(msg)
        for point_index, (actual_point, expected_point) in enumerate(
            zip(actual_line, expected_line, strict=True)
        ):
            if not _near(actual_point, expected_point, tolerance):
                msg = (
                    f"{label}: polyline {index} point {point_index} "
                    f"expected {expected_point}, got {actual_point} (tol {tolerance} mm)"
                )
                raise AssertionError(msg)


def _assert_bbox(
    label: str,
    actual: tuple[float, float, float, float],
    expected: list,
    tolerance: float,
) -> None:
    rounded = tuple(round(value, 4) for value in actual)
    if len(expected) != 4 or not _near(actual, expected, tolerance):
        msg = f"{label}: bbox expected {expected}, got {rounded} (tol {tolerance} mm)"
        raise AssertionError(msg)


def _assert_circle(
    label: str,
    polylines: list[list[tuple[float, float]]],
    circle: dict,
    *,
    viewport: list,
) -> None:
    cx = float(circle["cx"])
    cy = float(circle["cy"])
    radius = float(circle["r"])
    radial_tolerance = float(circle.get("radial_tolerance_mm", 0.15))
    boundary_tolerance = float(circle.get("boundary_tolerance_mm", 0.05))
    width = float(viewport[0])
    height = float(viewport[1])
    offenders: list[tuple[float, float]] = []
    for polyline in polylines:
        for x, y in polyline:
            radial = abs(math.hypot(x - cx, y - cy) - radius)
            on_circle = radial <= radial_tolerance
            on_boundary = (
                abs(x) <= boundary_tolerance
                or abs(y) <= boundary_tolerance
                or abs(x - width) <= boundary_tolerance
                or abs(y - height) <= boundary_tolerance
            )
            if not on_circle and not on_boundary:
                offenders.append((x, y))
    if offenders:
        msg = (
            f"{label}: {len(offenders)} points are neither on the circle "
            f"(cx={cx}, cy={cy}, r={radius} ± {radial_tolerance} mm) "
            f"nor on the viewport boundary\nfirst={offenders[:6]}"
        )
        raise AssertionError(msg)


def _parse_move_line_path(path_data: str) -> list[tuple[float, float]]:
    tokens = _TOKEN_RE.findall(path_data)
    points: list[tuple[float, float]] = []
    command = ""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            continue
        if command not in {"M", "L"}:
            msg = f"Golden oracle only accepts M/L output, saw {command!r} in {path_data!r}"
            raise AssertionError(msg)
        if index + 1 >= len(tokens):
            msg = f"Incomplete coordinate pair in {path_data!r}"
            raise AssertionError(msg)
        points.append((float(tokens[index]), float(tokens[index + 1])))
        index += 2
        if command == "M":
            command = "L"
    return points


def _near(
    actual: tuple[float, ...],
    expected: list | tuple,
    tolerance: float,
) -> bool:
    if len(actual) != len(expected):
        return False
    return all(
        abs(float(left) - float(right)) <= tolerance
        for left, right in zip(actual, expected, strict=True)
    )


def _expectation_summary(expectation: dict) -> str:
    parts: list[str] = []
    if "bbox_mm" in expectation:
        parts.append(f"bbox {expectation['bbox_mm']}")
    if "polylines_mm" in expectation:
        parts.append(f"{len(expectation['polylines_mm'])} polylines")
    if "min_points" in expectation:
        parts.append(f"min_points {expectation['min_points']}")
    return ", ".join(parts) or "geometry"


def _dump(value: object) -> str:
    return json.dumps(value)
