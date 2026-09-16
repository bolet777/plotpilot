"""Plot motion settings passed to axicli (optional overrides only)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Reference defaults from axidraw_conf.py (display only; not sent when override is None).
REFERENCE_PEN_DOWN_SPEED = 25
REFERENCE_PEN_UP_SPEED = 75
REFERENCE_ACCELERATION = 75

SPEED_MIN = 1
SPEED_MAX = 100
ACCEL_MIN = 1
ACCEL_MAX = 100
MODEL_MIN = 1
MODEL_MAX = 7

AXIDRAW_MODELS: dict[int, str] = {
    1: "AxiDraw V2, V3, or SE/A4",
    2: "AxiDraw V3/A3 or SE/A3",
    3: "AxiDraw V3 XLX",
    4: "AxiDraw MiniKit",
    5: "AxiDraw SE/A1",
    6: "AxiDraw SE/A2",
    7: "AxiDraw V3/B6",
}


class PlotSettingsValidationError(ValueError):
    """Raised when plot settings are outside axicli-supported ranges."""


@dataclass(frozen=True, slots=True)
class PlotSettings:
    """None fields mean omit CLI flag (use axicli / axidraw_conf defaults)."""

    pen_down_speed: int | None = None
    pen_up_speed: int | None = None
    acceleration: int | None = None
    model: int | None = None

    def validate(self) -> None:
        if self.pen_down_speed is not None and not SPEED_MIN <= self.pen_down_speed <= SPEED_MAX:
            raise PlotSettingsValidationError(
                f"Pen-down speed must be {SPEED_MIN}–{SPEED_MAX}.",
            )
        if self.pen_up_speed is not None and not SPEED_MIN <= self.pen_up_speed <= SPEED_MAX:
            raise PlotSettingsValidationError(
                f"Pen-up speed must be {SPEED_MIN}–{SPEED_MAX}.",
            )
        if self.acceleration is not None and not ACCEL_MIN <= self.acceleration <= ACCEL_MAX:
            raise PlotSettingsValidationError(
                f"Acceleration must be {ACCEL_MIN}–{ACCEL_MAX}.",
            )
        if self.model is not None and not MODEL_MIN <= self.model <= MODEL_MAX:
            raise PlotSettingsValidationError(
                f"Model must be {MODEL_MIN}–{MODEL_MAX}.",
            )

    @property
    def has_overrides(self) -> bool:
        return any(
            value is not None
            for value in (
                self.pen_down_speed,
                self.pen_up_speed,
                self.acceleration,
                self.model,
            )
        )


def build_axicli_plot_argv(
    cli: str,
    svg_path: Path,
    settings: PlotSettings | None = None,
) -> list[str]:
    """Build axicli argv for a single-layer hardware plot."""
    plot_settings = settings if settings is not None else PlotSettings()
    plot_settings.validate()
    argv = [cli, str(svg_path), "-m", "plot", "-c", "1"]
    if plot_settings.pen_down_speed is not None:
        argv.extend(["-s", str(plot_settings.pen_down_speed)])
    if plot_settings.pen_up_speed is not None:
        argv.extend(["-S", str(plot_settings.pen_up_speed)])
    if plot_settings.acceleration is not None:
        argv.extend(["-a", str(plot_settings.acceleration)])
    if plot_settings.model is not None:
        argv.extend(["-L", str(plot_settings.model)])
    return argv
