"""Golden SVG oracles for the plot-preparation pipeline.

Expected millimeters are hand-calculated. XFAIL marks name audit ids from
docs/AUDIT-2026-09-30.md. They must start passing when the referenced bug is
fixed; do not edit the expected JSON to match current broken output.
"""

from __future__ import annotations

import json

import pytest

from golden_oracle import (
    GOLDEN_ROOT,
    assert_golden,
    load_expectation,
    observe_golden,
    polyline_bbox,
)

_CSS_PX_MM = 25.4 / 96


@pytest.mark.parametrize(
    "case",
    [
        "square/identity_inside",
        "viewbox/carre_a4_rotate",
        "transforms/translate_rect",
        "paths/relative_multisubpath",
        "viewbox/b9_preserve_aspect_meet",
        "styles/b6_root_style_document",
        "square/b3_viewboxless_rect_plus_line",
        "groups/b10_marker_viewbox_10",
    ],
)
def test_golden_known_good(case: str) -> None:
    assert_golden(case)


def test_b5_whole_document_uses_css_pixels() -> None:
    assert_golden("layers/b5_px_inkscape_layer", only="document")


def test_b7_parent_layer_keeps_transform() -> None:
    assert_golden("layers/b7_nested_transformed_layer", only="parent")


def test_b8_fill_only_fixture_records_pending_decision() -> None:
    """B8/Q1: record the fill-only case without choosing a plot policy."""
    expected = load_expectation("styles/b8_fill_only")
    svg_text = (GOLDEN_ROOT / "styles" / "b8_fill_only.svg").read_text(encoding="utf-8")
    assert expected["policy"] == "pending"
    assert expected["decision"] == "Q1"
    assert 'fill="#336699"' in svg_text
    assert "stroke" not in svg_text


def test_b1_square_exit_and_reenter_has_no_diagonal() -> None:
    assert_golden("clipping/b1_square_exit_reenter")


def test_b1_scaled_square_exit_and_reenter_has_no_diagonal() -> None:
    assert_golden("clipping/b1_scaled_square_exit_reenter")


def test_b2_near_complete_arc_keeps_circle_bounds() -> None:
    assert_golden("paths/b2_near_complete_arc")


def test_b3_viewboxless_small_rect_is_css_pixels() -> None:
    assert_golden("square/b3_viewboxless_rect")


def test_b3_unrelated_geometry_does_not_change_rect_scale() -> None:
    small = observe_golden("square/b3_viewboxless_rect")
    large = observe_golden("square/b3_viewboxless_rect_plus_line")
    assert small.error is None, small.error
    assert large.error is None, large.error
    assert small.polylines_mm is not None
    assert large.polylines_mm is not None
    large_rects = [polyline for polyline in large.polylines_mm if len(polyline) >= 5]
    assert len(large_rects) == 1
    expected = (
        10 * _CSS_PX_MM,
        10 * _CSS_PX_MM,
        110 * _CSS_PX_MM,
        60 * _CSS_PX_MM,
    )
    assert polyline_bbox(small.polylines_mm) == pytest.approx(expected, abs=0.02)
    assert polyline_bbox(large_rects) == pytest.approx(expected, abs=0.02)


def test_b5_isolated_layer_matches_document_scale() -> None:
    assert_golden("layers/b5_px_inkscape_layer", only="isolated")


def test_b6_isolated_layer_keeps_root_style() -> None:
    assert_golden("styles/b6_layer1_isolated")


def test_b7_child_layer_keeps_parent_transform() -> None:
    assert_golden("layers/b7_nested_transformed_layer", only="child")


def test_b10_marker_viewbox_does_not_rescale_page() -> None:
    assert_golden("groups/b10_marker_viewbox_200")


def test_b8_expected_file_does_not_choose_geometry() -> None:
    raw = (GOLDEN_ROOT / "styles" / "b8_fill_only.expected.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert "polylines_mm" not in payload
    assert "bbox_mm" not in payload
