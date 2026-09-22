"""Physical artwork placement relative to the machine viewport (Qt-free)."""

from __future__ import annotations

import math
from dataclasses import dataclass

# UI may clamp to this range; core validates finiteness and scale > 0.
DEFAULT_SCALE_MIN = 0.1
DEFAULT_SCALE_MAX = 10.0


@dataclass(frozen=True, slots=True)
class ArtworkTransform:
    """Uniform scale and translation in millimeters (no rotation)."""

    x_mm: float = 0.0
    y_mm: float = 0.0
    scale: float = 1.0

    def validate(self) -> None:
        if not math.isfinite(self.x_mm) or not math.isfinite(self.y_mm):
            msg = "Artwork position must be finite."
            raise ArtworkTransformError(msg)
        if not math.isfinite(self.scale) or self.scale <= 0.0:
            msg = "Artwork scale must be a finite number greater than zero."
            raise ArtworkTransformError(msg)

    def apply_point(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        self.validate()
        return self.x_mm + x_mm * self.scale, self.y_mm + y_mm * self.scale

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
    return ArtworkTransform(x_mm=transform.x_mm, y_mm=transform.y_mm, scale=percent / 100.0)
