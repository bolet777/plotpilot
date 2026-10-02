"""X/Y slider travel derived from unscaled artwork bounds, scale, and printable area."""

from __future__ import annotations

import pytest

from plotpilot.ui.transform_slider_mapping import (
    ArtworkBoundsMm,
    artwork_bounds_from_polylines,
    axis_translation_limits,
)


def test_artwork_smaller_than_printable_area_at_100_percent() -> None:
    # 30 mm artwork inside a 300 mm printable span.
    min_x, max_x = axis_translation_limits(
        artwork_min_mm=10.0,
        artwork_max_mm=40.0,
        scale=1.0,
        printable_min_mm=0.0,
        printable_max_mm=300.0,
    )
    assert min_x == pytest.approx(0.0 - 40.0)
    assert max_x == pytest.approx(300.0 - 10.0)
    assert 40.0 + min_x == pytest.approx(0.0)
    assert 10.0 + max_x == pytest.approx(300.0)


def test_artwork_larger_than_printable_area_at_200_percent() -> None:
    # 200 mm artwork at 200% is 400 mm; printable span is 280 mm.
    min_x, max_x = axis_translation_limits(
        artwork_min_mm=0.0,
        artwork_max_mm=200.0,
        scale=2.0,
        printable_min_mm=10.0,
        printable_max_mm=290.0,
    )
    assert min_x == pytest.approx(10.0 - 400.0)
    assert max_x == pytest.approx(290.0 - 0.0)
    assert 400.0 + min_x == pytest.approx(10.0)
    assert 0.0 + max_x == pytest.approx(290.0)
    assert min_x < -300.0


def test_x_translation_reaches_printable_left_and_right() -> None:
    min_x, max_x = axis_translation_limits(
        artwork_min_mm=20.0,
        artwork_max_mm=80.0,
        scale=2.0,
        printable_min_mm=12.0,
        printable_max_mm=250.0,
    )
    scaled_left = 20.0 * 2.0
    scaled_right = 80.0 * 2.0
    assert scaled_right + min_x == pytest.approx(12.0)
    assert scaled_left + max_x == pytest.approx(250.0)


def test_y_translation_reaches_printable_top_and_bottom() -> None:
    min_y, max_y = axis_translation_limits(
        artwork_min_mm=5.0,
        artwork_max_mm=50.0,
        scale=2.0,
        printable_min_mm=8.0,
        printable_max_mm=180.0,
    )
    scaled_top = 5.0 * 2.0
    scaled_bottom = 50.0 * 2.0
    assert scaled_bottom + min_y == pytest.approx(8.0)
    assert scaled_top + max_y == pytest.approx(180.0)


def test_margins_shift_translation_limits() -> None:
    # 15 mm horizontal inset on a 300 mm work area: printable x is 15..285.
    limits = axis_translation_limits(
        artwork_min_mm=0.0,
        artwork_max_mm=100.0,
        scale=1.0,
        printable_min_mm=15.0,
        printable_max_mm=285.0,
    )
    assert limits == pytest.approx((15.0 - 100.0, 285.0 - 0.0))


def test_scale_is_applied_once_to_unscaled_bounds() -> None:
    once = axis_translation_limits(
        artwork_min_mm=10.0,
        artwork_max_mm=90.0,
        scale=2.0,
        printable_min_mm=0.0,
        printable_max_mm=300.0,
    )
    same_as_pre_scaled_bounds = axis_translation_limits(
        artwork_min_mm=20.0,
        artwork_max_mm=180.0,
        scale=1.0,
        printable_min_mm=0.0,
        printable_max_mm=300.0,
    )
    applied_twice = axis_translation_limits(
        artwork_min_mm=20.0,
        artwork_max_mm=180.0,
        scale=2.0,
        printable_min_mm=0.0,
        printable_max_mm=300.0,
    )
    assert once == pytest.approx(same_as_pre_scaled_bounds)
    assert once != pytest.approx(applied_twice)


def test_nonzero_artwork_origin_and_bounds() -> None:
    bounds = artwork_bounds_from_polylines(
        (
            ((20.0, 30.0), (80.0, 30.0), (80.0, 70.0)),
            ((25.0, 90.0), (40.0, 90.0)),
        ),
    )
    assert bounds == ArtworkBoundsMm(20.0, 80.0, 30.0, 90.0)
    assert bounds is not None
    min_x, max_x = axis_translation_limits(
        artwork_min_mm=bounds.min_x_mm,
        artwork_max_mm=bounds.max_x_mm,
        scale=1.0,
        printable_min_mm=10.0,
        printable_max_mm=200.0,
    )
    min_y, max_y = axis_translation_limits(
        artwork_min_mm=bounds.min_y_mm,
        artwork_max_mm=bounds.max_y_mm,
        scale=1.0,
        printable_min_mm=10.0,
        printable_max_mm=250.0,
    )
    assert min_x == pytest.approx(10.0 - 80.0)
    assert max_x == pytest.approx(200.0 - 20.0)
    assert min_y == pytest.approx(10.0 - 90.0)
    assert max_y == pytest.approx(250.0 - 30.0)


def test_empty_polylines_have_no_bounds() -> None:
    assert artwork_bounds_from_polylines(()) is None
    assert artwork_bounds_from_polylines(((),)) is None
