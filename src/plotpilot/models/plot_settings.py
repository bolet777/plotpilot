"""Plot motion settings passed to axicli (optional overrides only)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Reference defaults from axidraw_conf.py (display only; not sent when override is None).
REFERENCE_PEN_DOWN_SPEED = 25
REFERENCE_PEN_UP_SPEED = 75
REFERENCE_ACCELERATION = 75
REFERENCE_PEN_UP_POSITION = 60
REFERENCE_PEN_DOWN_POSITION = 30

SPEED_MIN = 1
SPEED_MAX = 100
ACCEL_MIN = 1
ACCEL_MAX = 100
PEN_POS_MIN = 0
PEN_POS_MAX = 100
MODEL_MIN = 1
MODEL_MAX = 7

# axicli 3.9.6 --reordering values (see specs/023-axicli-controls/research.md).
REORDERING_BASIC = 1
REORDERING_FULL = 2
REORDERING_STRICT = 4
REORDERING_ALLOWED = frozenset({REORDERING_BASIC, REORDERING_FULL, REORDERING_STRICT})

# (value, label). None omits -G (axidraw_conf.py decides).
PATH_ORDER_OPTIONS: tuple[tuple[int | None, str], ...] = (
    (None, "Driver default"),
    (REORDERING_STRICT, "None / strict file order"),
    (REORDERING_BASIC, "Basic reorder"),
    (REORDERING_FULL, "Full reorder + reverse"),
)

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
    """Optional fields are omitted from argv so the driver config stays authoritative.

    ``path_reordering`` defaults to strict file order (``-G4``) so path order does
    not depend on ``axidraw_conf.py``. ``None`` is the explicit driver-default policy.
    axicli orientation is always preserved (``-N``); there is no enable flag. Page
    rotation is a PlotPilot-side ``ArtworkTransform`` concern, not a plot setting.
    """

    pen_down_speed: int | None = None
    pen_up_speed: int | None = None
    acceleration: int | None = None
    model: int | None = None
    path_reordering: int | None = REORDERING_STRICT
    pen_pos_up: int | None = None
    pen_pos_down: int | None = None
    const_speed: bool = False

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
        if self.pen_pos_up is not None and not PEN_POS_MIN <= self.pen_pos_up <= PEN_POS_MAX:
            raise PlotSettingsValidationError(
                f"Pen-up position must be {PEN_POS_MIN}–{PEN_POS_MAX}.",
            )
        if self.pen_pos_down is not None and not PEN_POS_MIN <= self.pen_pos_down <= PEN_POS_MAX:
            raise PlotSettingsValidationError(
                f"Pen-down position must be {PEN_POS_MIN}–{PEN_POS_MAX}.",
            )
        if self.model is not None and not MODEL_MIN <= self.model <= MODEL_MAX:
            raise PlotSettingsValidationError(
                f"Model must be {MODEL_MIN}–{MODEL_MAX}.",
            )
        if self.path_reordering is not None and self.path_reordering not in REORDERING_ALLOWED:
            raise PlotSettingsValidationError(
                "Path ordering must be driver default or axicli -G 1, 2, or 4.",
            )
        if not isinstance(self.const_speed, bool):
            raise PlotSettingsValidationError("Constant speed must be on or off.")

    @property
    def has_overrides(self) -> bool:
        optional = (
            self.pen_down_speed,
            self.pen_up_speed,
            self.acceleration,
            self.model,
            self.pen_pos_up,
            self.pen_pos_down,
        )
        if any(value is not None for value in optional):
            return True
        if self.const_speed:
            return True
        return self.path_reordering != REORDERING_STRICT

    @property
    def optimize_path_order(self) -> bool:
        return self.path_reordering == REORDERING_BASIC


def append_axicli_motion_argv(argv: list[str], settings: PlotSettings) -> None:
    """Append motion flags shared by plot and preview. Each flag is added at most once."""
    if settings.pen_down_speed is not None:
        argv.extend(["-s", str(settings.pen_down_speed)])
    if settings.pen_up_speed is not None:
        argv.extend(["-S", str(settings.pen_up_speed)])
    if settings.acceleration is not None:
        argv.extend(["-a", str(settings.acceleration)])
    if settings.pen_pos_up is not None:
        argv.extend(["-u", str(settings.pen_pos_up)])
    if settings.pen_pos_down is not None:
        argv.extend(["-d", str(settings.pen_pos_down)])
    if settings.model is not None:
        argv.extend(["-L", str(settings.model)])
    if settings.path_reordering is not None:
        argv.extend(["-G", str(settings.path_reordering)])
    # Always preserve SVG orientation. axicli cannot force auto-rotate on, and
    # the rotation direction is config-only. See specs/023-axicli-controls/research.md.
    # User-chosen rotation is applied by PlotPilot (ArtworkTransform.orientation)
    # to the prepared SVG before it reaches axicli.
    argv.append("-N")
    if settings.const_speed:
        argv.append("-C")


def build_axicli_plot_argv(
    cli: str,
    svg_path: Path,
    settings: PlotSettings | None = None,
) -> list[str]:
    """Build axicli argv for a single-layer hardware plot."""
    plot_settings = settings if settings is not None else PlotSettings()
    plot_settings.validate()
    argv = [cli, str(svg_path), "-m", "plot", "-c", "1"]
    append_axicli_motion_argv(argv, plot_settings)
    return argv


def build_axicli_preview_argv(
    cli: str,
    svg_path: Path,
    settings: PlotSettings | None = None,
) -> list[str]:
    """Build axicli argv for offline preview time/distance estimate."""
    plot_settings = settings if settings is not None else PlotSettings()
    plot_settings.validate()
    argv = [cli, str(svg_path), "-v", "-T"]
    append_axicli_motion_argv(argv, plot_settings)
    return argv
