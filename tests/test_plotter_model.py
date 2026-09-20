"""Verified AxiDraw model travel table."""

from __future__ import annotations

import pytest

from plotpilot.models.plotter_model import (
    MODEL_MAX,
    MODEL_MIN,
    UnknownPlotterModelError,
    all_plotter_models,
    get_plotter_model_info,
)

_INCH = 25.4

_EXPECTED = {
    1: ("AxiDraw V2, V3, or SE/A4", 11.81, 8.58),
    2: ("AxiDraw V3/A3 or SE/A3", 16.93, 11.69),
    3: ("AxiDraw V3 XLX", 23.42, 8.58),
    4: ("AxiDraw MiniKit", 6.30, 4.00),
    5: ("AxiDraw SE/A1", 34.02, 23.39),
    6: ("AxiDraw SE/A2", 23.39, 17.01),
    7: ("AxiDraw V3/B6", 7.48, 5.51),
}


def test_all_model_codes_exist() -> None:
    models = all_plotter_models()
    assert len(models) == 7
    assert [m.code for m in models] == list(range(MODEL_MIN, MODEL_MAX + 1))


@pytest.mark.parametrize("code", range(MODEL_MIN, MODEL_MAX + 1))
def test_model_display_names_and_dimensions(code: int) -> None:
    name, x_in, y_in = _EXPECTED[code]
    info = get_plotter_model_info(code)
    assert info.display_name == name
    assert info.max_width_mm == pytest.approx(x_in * _INCH)
    assert info.max_height_mm == pytest.approx(y_in * _INCH)


def test_invalid_model_code_rejected() -> None:
    with pytest.raises(UnknownPlotterModelError):
        get_plotter_model_info(0)
    with pytest.raises(UnknownPlotterModelError):
        get_plotter_model_info(8)
