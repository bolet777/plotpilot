"""Physical artwork placement relative to the machine viewport (Qt-free).

Placement is ``machine = translation + scale * orient(document_point)`` where
``orient`` rotates the *document page* by a multiple of 90° so the rotated page
still starts at (0, 0). The rotation is done by PlotPilot before clipping;
axicli always receives ``-N`` and never rotates on its own.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import StrEnum

# UI may clamp to this range; core validates finiteness and scale > 0.
DEFAULT_SCALE_MIN = 0.1
DEFAULT_SCALE_MAX = 10.0

ROTATION_DEGREES = (0, 90, 180, 270)


class ArtworkOrientation(StrEnum):
    """User intent for page orientation. ``AUTO`` is resolved against the printable area."""

    PRESERVED = "preserved"
    AUTO = "auto"
    ROTATE_90_CW = "cw"
    ROTATE_90_CCW = "ccw"


# axicli ``auto_rotate_ccw`` defaults to counter-clockwise; mirror that for AUTO.
AUTO_ROTATION_DEGREES = 270


@dataclass(frozen=True, slots=True)
class ArtworkTransform:
    """Uniform scale, translation in millimeters, and a page orientation policy."""

    x_mm: float = 0.0
    y_mm: float = 0.0
    scale: float = 1.0
    orientation: ArtworkOrientation = ArtworkOrientation.PRESERVED

    def validate(self) -> None:
        if not math.isfinite(self.x_mm) or not math.isfinite(self.y_mm):
            msg = "Artwork position must be finite."
            raise ArtworkTransformError(msg)
        if not math.isfinite(self.scale) or self.scale <= 0.0:
            msg = "Artwork scale must be a finite number greater than zero."
            raise ArtworkTransformError(msg)
        if not isinstance(self.orientation, ArtworkOrientation):
            msg = "Artwork orientation must be preserved, auto, cw, or ccw."
            raise ArtworkTransformError(msg)

    def apply_point(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        """Place an already-oriented document point (translation and scale only)."""
        self.validate()
        return self.x_mm + x_mm * self.scale, self.y_mm + y_mm * self.scale

    @property
    def needs_page_size(self) -> bool:
        """True when placing points requires the document page size."""
        return self.orientation is not ArtworkOrientation.PRESERVED

    @classmethod
    def identity(cls) -> ArtworkTransform:
        return cls()


class ArtworkTransformError(ValueError):
    """Invalid transform parameters."""


def scale_percent(transform: ArtworkTransform) -> float:
    return transform.scale * 100.0


def transform_from_scale_percent(
    transform: ArtworkTransform,
    percent: float,
) -> ArtworkTransform:
    if not math.isfinite(percent) or percent <= 0.0:
        msg = "Scale must be a finite percentage greater than zero."
        raise ArtworkTransformError(msg)
    return replace(transform, scale=percent / 100.0)


def parse_artwork_orientation(value: object) -> ArtworkOrientation | None:
    """Coerce a stored value to an orientation; ``None`` when unrecognized."""
    if isinstance(value, ArtworkOrientation):
        return value
    if isinstance(value, str):
        try:
            return ArtworkOrientation(value.strip().lower())
        except ValueError:
            return None
    return None


def resolve_rotation_degrees(
    orientation: ArtworkOrientation,
    *,
    page_width_mm: float,
    page_height_mm: float,
    printable_width_mm: float,
    printable_height_mm: float,
) -> int:
    """Effective clockwise rotation (0, 90, 180, 270) for *orientation*.

    ``AUTO`` rotates 90° counter-clockwise only when the page and the printable
    area disagree on portrait vs landscape. Square pages or printable areas never
    trigger a rotation.
    """
    if orientation is ArtworkOrientation.ROTATE_90_CW:
        return 90
    if orientation is ArtworkOrientation.ROTATE_90_CCW:
        return 270
    if orientation is ArtworkOrientation.AUTO:
        page = _aspect(page_width_mm, page_height_mm)
        printable = _aspect(printable_width_mm, printable_height_mm)
        if page is not None and printable is not None and page != printable:
            return AUTO_ROTATION_DEGREES
        return 0
    return 0


def oriented_page_size(
    page_width_mm: float,
    page_height_mm: float,
    rotation_degrees: int,
) -> tuple[float, float]:
    """Page width × height after rotating by *rotation_degrees*."""
    _check_rotation(rotation_degrees)
    if rotation_degrees in (90, 270):
        return page_height_mm, page_width_mm
    return page_width_mm, page_height_mm


def orient_point(
    x_mm: float,
    y_mm: float,
    rotation_degrees: int,
    *,
    page_width_mm: float,
    page_height_mm: float,
) -> tuple[float, float]:
    """Rotate a document point about the page so the rotated page starts at (0, 0).

    Angles are clockwise on a y-down page (SVG and machine convention).
    """
    _check_rotation(rotation_degrees)
    if rotation_degrees == 90:
        return page_height_mm - y_mm, x_mm
    if rotation_degrees == 180:
        return page_width_mm - x_mm, page_height_mm - y_mm
    if rotation_degrees == 270:
        return y_mm, page_width_mm - x_mm
    return x_mm, y_mm


def rotation_label(rotation_degrees: int) -> str:
    """Short human label used by the UI note and status lines."""
    _check_rotation(rotation_degrees)
    return {
        0: "no rotation",
        90: "rotated 90° CW",
        180: "rotated 180°",
        270: "rotated 90° CCW",
    }[rotation_degrees]


def _aspect(width_mm: float, height_mm: float) -> str | None:
    if not math.isfinite(width_mm) or not math.isfinite(height_mm):
        return None
    if width_mm <= 0.0 or height_mm <= 0.0 or math.isclose(width_mm, height_mm):
        return None
    return "portrait" if height_mm > width_mm else "landscape"


def _check_rotation(rotation_degrees: int) -> None:
    if rotation_degrees not in ROTATION_DEGREES:
        msg = "Rotation must be 0, 90, 180, or 270 degrees."
        raise ArtworkTransformError(msg)
