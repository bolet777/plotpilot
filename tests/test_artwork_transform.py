"""ArtworkTransform validation and helpers."""

from __future__ import annotations

import math

import pytest

from plotpilot.models.artwork_transform import (
    ArtworkTransform,
    ArtworkTransformError,
    scale_percent,
    transform_from_scale_percent,
)


def test_identity_defaults() -> None:
    t = ArtworkTransform.identity()
    assert t.x_mm == 0.0
    assert t.y_mm == 0.0
    assert t.scale == 1.0


def test_apply_point_translation_and_scale() -> None:
    t = ArtworkTransform(x_mm=10.0, y_mm=-5.0, scale=2.0)
    assert t.apply_point(3.0, 4.0) == (16.0, 3.0)


def test_rejects_non_positive_scale() -> None:
    with pytest.raises(ArtworkTransformError):
        ArtworkTransform(scale=0.0).validate()


def test_rejects_nan() -> None:
    with pytest.raises(ArtworkTransformError):
        ArtworkTransform(x_mm=math.nan).validate()


def test_scale_percent_round_trip() -> None:
    t = ArtworkTransform(scale=1.25)
    assert scale_percent(t) == pytest.approx(125.0)
    t2 = transform_from_scale_percent(t, 50.0)
    assert t2.scale == pytest.approx(0.5)
