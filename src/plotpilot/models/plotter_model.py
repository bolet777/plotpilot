"""Verified AxiDraw model travel limits (axicli / axidraw_conf 3.9.6)."""

from __future__ import annotations

from dataclasses import dataclass

# Official inch constants from axidrawinternal/axidraw_conf.py (AxiDraw Software 3.9.6).
_INCH_TO_MM = 25.4

_MODEL_TRAVEL_IN: dict[int, tuple[tuple[str, str], tuple[float, float]]] = {
    1: (("AxiDraw V2, V3, or SE/A4", "x_travel_default"), (11.81, 8.58)),
    2: (("AxiDraw V3/A3 or SE/A3", "x_travel_V3A3"), (16.93, 11.69)),
    3: (("AxiDraw V3 XLX", "x_travel_V3XLX"), (23.42, 8.58)),
    4: (("AxiDraw MiniKit", "x_travel_MiniKit"), (6.30, 4.00)),
    5: (("AxiDraw SE/A1", "x_travel_SEA1"), (34.02, 23.39)),
    6: (("AxiDraw SE/A2", "x_travel_SEA2"), (23.39, 17.01)),
    7: (("AxiDraw V3/B6", "x_travel_V3B6"), (7.48, 5.51)),
}

MODEL_MIN = 1
MODEL_MAX = 7


class UnknownPlotterModelError(ValueError):
    """Raised when a model code is outside the official 1–7 range."""


@dataclass(frozen=True, slots=True)
class PlotterModelInfo:
    code: int
    display_name: str
    max_width_mm: float
    max_height_mm: float


def _mm_from_inches(value_in: float) -> float:
    return value_in * _INCH_TO_MM


def get_plotter_model_info(code: int) -> PlotterModelInfo:
    """Return travel limits for an explicit axicli model code (1–7)."""
    if code not in _MODEL_TRAVEL_IN:
        raise UnknownPlotterModelError(f"Model must be {MODEL_MIN}–{MODEL_MAX}.")
    (display_name, _conf_key), (x_in, y_in) = _MODEL_TRAVEL_IN[code]
    return PlotterModelInfo(
        code=code,
        display_name=display_name,
        max_width_mm=_mm_from_inches(x_in),
        max_height_mm=_mm_from_inches(y_in),
    )


def all_plotter_models() -> tuple[PlotterModelInfo, ...]:
    return tuple(get_plotter_model_info(code) for code in sorted(_MODEL_TRAVEL_IN))
