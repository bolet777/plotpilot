"""Task #6: vpype spike vs current golden geometry (evaluation only)."""

from __future__ import annotations

import io
import time

import pytest
import vpype
from experiments.vpype.adapter import ClipBackend, prepare_vpype_polylines_mm

from golden_oracle import (
    GOLDEN_ROOT,
    GoldenObservation,
    _preparation_by_id,
    _prepare,
    _source_svg,
    _transform,
    load_expectation,
    polyline_bbox,
)
from plotpilot.geometry.plot_viewport import PlotViewportError, prepare_positioned_plot_svg
from plotpilot.models.artwork_transform import ArtworkTransform

pytest.importorskip("vpype")

_GOLDEN_CASES: list[tuple[str, str | None]] = [
    ("square/identity_inside", None),
    ("viewbox/carre_a4_rotate", None),
    ("transforms/translate_rect", None),
    ("paths/relative_multisubpath", None),
    ("viewbox/b9_preserve_aspect_meet", None),
    ("styles/b6_root_style_document", None),
    ("square/b3_viewboxless_rect_plus_line", None),
    ("groups/b10_marker_viewbox_10", None),
    ("clipping/b1_square_exit_reenter", None),
    ("clipping/b1_scaled_square_exit_reenter", None),
    ("paths/b2_near_complete_arc", None),
    ("square/b3_viewboxless_rect", None),
    ("layers/b5_px_inkscape_layer", "document"),
    ("layers/b5_px_inkscape_layer", "isolated"),
    ("layers/b7_nested_transformed_layer", "parent"),
    ("layers/b7_nested_transformed_layer", "child"),
    ("styles/b6_layer1_isolated", "isolated"),
    ("groups/b10_marker_viewbox_200", None),
]

ComparisonVerdict = str  # SAME | VPYPE BETTER | CURRENT BETTER | SEMANTIC DIFFERENCE | UNSUPPORTED


def _classify_bbox(
    current: GoldenObservation,
    vpype_obs: GoldenObservation,
    tolerance_mm: float,
) -> ComparisonVerdict:
    if current.error is not None and vpype_obs.error is not None:
        return "SAME"
    if current.error is not None:
        return "CURRENT BETTER"
    if vpype_obs.error is not None:
        return "VPYPE BETTER" if False else "CURRENT BETTER"
    assert current.polylines_mm is not None
    assert vpype_obs.polylines_mm is not None
    cb = polyline_bbox(current.polylines_mm)
    vb = polyline_bbox(vpype_obs.polylines_mm)
    bbox_match = all(abs(a - b) <= tolerance_mm for a, b in zip(cb, vb, strict=True))
    same_count = len(current.polylines_mm) == len(vpype_obs.polylines_mm)
    if bbox_match and same_count:
        return "SAME"
    if bbox_match:
        return "SEMANTIC DIFFERENCE"
    return "CURRENT BETTER"


@pytest.mark.parametrize(("case", "preparation_id"), _GOLDEN_CASES)
def test_vpype_hybrid_matches_golden_bbox_and_topology(
    case: str,
    preparation_id: str | None,
) -> None:
    """vpype read + PlotPilot page mm map + Liang–Barsky vs golden oracle."""
    expectation = load_expectation(case)
    prep_id = preparation_id or "document"
    preparation = _preparation_by_id(expectation, prep_id)
    tolerance = float(expectation.get("tolerance_mm", 0.02))

    current = _prepare(case, expectation, preparation)
    svg_text = _source_svg(case, expectation, preparation)
    viewport = expectation["viewport_mm"]
    transform = _transform(expectation)
    vpype_polylines = prepare_vpype_polylines_mm(
        svg_text,
        viewport_width_mm=float(viewport[0]),
        viewport_height_mm=float(viewport[1]),
        transform=transform,
        clip_backend=ClipBackend.LIANG_BARSKY,
    )
    vpype_obs = GoldenObservation(polylines_mm=vpype_polylines, error=None)

    verdict = _classify_bbox(current, vpype_obs, tolerance)
    assert verdict == "SAME", (
        f"{case}[{prep_id}]: expected SAME, got {verdict}\n"
        f"current={current.error or polyline_bbox(current.polylines_mm or [])}\n"
        f"vpype={polyline_bbox(vpype_polylines)}"
    )


def test_b1_vpype_native_crop_matches_current_no_spurious_diagonal() -> None:
    case = "clipping/b1_square_exit_reenter"
    expectation = load_expectation(case)
    preparation = _preparation_by_id(expectation, "document")
    svg_text = _source_svg(case, expectation, preparation)
    viewport = expectation["viewport_mm"]
    transform = _transform(expectation)

    current = _prepare(case, expectation, preparation)
    assert current.polylines_mm is not None

    vpype_polylines = prepare_vpype_polylines_mm(
        svg_text,
        viewport_width_mm=float(viewport[0]),
        viewport_height_mm=float(viewport[1]),
        transform=transform,
        clip_backend=ClipBackend.VPYPE_RECT,
    )

    def _has_interior_diagonal(polylines: list[list[tuple[float, float]]]) -> bool:
        for polyline in polylines:
            for index in range(len(polyline) - 1):
                x0, y0 = polyline[index]
                x1, y1 = polyline[index + 1]
                if abs(x0 - x1) > 1.0 and abs(y0 - y1) > 1.0:
                    return True
        return False

    assert not _has_interior_diagonal(current.polylines_mm)
    assert not _has_interior_diagonal(vpype_polylines)
    assert len(vpype_polylines) == len(current.polylines_mm)


def test_vpype_fill_only_differs_from_stroke_only_current_policy() -> None:
    """B8/Q1: vpype plots fill-only shapes; PlotPilot skips non-stroked geometry."""
    svg_path = GOLDEN_ROOT / "styles" / "b8_fill_only.svg"
    svg_text = svg_path.read_text(encoding="utf-8")
    with pytest.raises(PlotViewportError):
        prepare_positioned_plot_svg(
            svg_text,
            viewport_width_mm=100.0,
            viewport_height_mm=100.0,
            transform=ArtworkTransform(),
        )
    vpype_polylines = prepare_vpype_polylines_mm(
        svg_text,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform(),
    )
    assert len(vpype_polylines) >= 1


def test_vpype_discards_text_and_keeps_stroked_lines() -> None:
    text_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<text x="10" y="50">Hi</text>'
        '<line x1="0" y1="0" x2="50" y2="50" stroke="black"/>'
        "</svg>"
    )
    lc, _, _ = vpype.read_svg(io.StringIO(text_svg), quantization=0.1, crop=False)
    assert len(lc) == 1


def test_vpype_stroke_none_still_imports_geometry() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<rect x="10" y="10" width="20" height="20" fill="none" stroke="none"/>'
        "</svg>"
    )
    lc, _, _ = vpype.read_svg(io.StringIO(svg), quantization=0.1, crop=False)
    assert len(lc) == 1


@pytest.mark.slow
def test_vpype_benchmark_smoke() -> None:
    """Rough wall-time ratio current prepare vs vpype read (not a CI gate)."""
    svg_text = (GOLDEN_ROOT / "square" / "identity_inside.svg").read_text(encoding="utf-8")

    def _bench_current() -> float:
        start = time.perf_counter()
        for _ in range(30):
            prepare_positioned_plot_svg(
                svg_text,
                viewport_width_mm=100.0,
                viewport_height_mm=100.0,
                transform=ArtworkTransform(),
            )
        return time.perf_counter() - start

    def _bench_vpype() -> float:
        start = time.perf_counter()
        for _ in range(30):
            prepare_vpype_polylines_mm(
                svg_text,
                viewport_width_mm=100.0,
                viewport_height_mm=100.0,
                transform=ArtworkTransform(),
            )
        return time.perf_counter() - start

    current_s = _bench_current()
    vpype_s = _bench_vpype()
    assert current_s > 0 and vpype_s > 0
