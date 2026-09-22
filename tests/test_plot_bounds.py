"""Plot bounds preflight service."""

from __future__ import annotations

from plotpilot.models.plot_bounds import BoundsStatus
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_model import get_plotter_model_info
from plotpilot.services.bounds_service import check_plot_bounds, plot_bounds_block_message

_A4_PORTRAIT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm"><path d="M0 0"/></svg>'
)
_A3_SHEET = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="420mm"><path d="M0 0"/></svg>'
)
_A4_LANDSCAPE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm"><path d="M0 0"/></svg>'
)
_INCH_DOC = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="8in" height="6in"><path d="M0 0"/></svg>'
)
_PX_DOC = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="480px" height="480px"><path d="M0 0"/></svg>'
)
_OVERSIZE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="500mm" height="500mm"><path d="M0 0"/></svg>'
)


def test_a4_portrait_fits_model_1() -> None:
    result = check_plot_bounds(_A4_PORTRAIT, PlotSettings(model=1))
    assert result.status is BoundsStatus.OK


def test_a3_sheet_fits_model_2() -> None:
    result = check_plot_bounds(_A3_SHEET, PlotSettings(model=2))
    assert result.status is BoundsStatus.OK


def test_inch_and_px_documents_parse() -> None:
    assert check_plot_bounds(_INCH_DOC, PlotSettings(model=1)).status is BoundsStatus.OK
    assert check_plot_bounds(_PX_DOC, PlotSettings(model=3)).status is BoundsStatus.OK


def test_width_exceeds_model_1() -> None:
    result = check_plot_bounds(_OVERSIZE, PlotSettings(model=1))
    assert result.status is BoundsStatus.OUT_OF_BOUNDS
    assert plot_bounds_block_message(_OVERSIZE, PlotSettings(model=1)) is None


def test_a3_on_a4_model_out_of_bounds() -> None:
    result = check_plot_bounds(_A3_SHEET, PlotSettings(model=1))
    assert result.status is BoundsStatus.OUT_OF_BOUNDS


def test_exact_boundary_ok() -> None:
    model = get_plotter_model_info(7)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{model.max_width_mm}mm" height="{model.max_height_mm}mm">'
        f'<path d="M0 0"/></svg>'
    )
    result = check_plot_bounds(svg, PlotSettings(model=7))
    assert result.status is BoundsStatus.OK


def test_default_cli_unknown_model() -> None:
    result = check_plot_bounds(_A4_PORTRAIT, PlotSettings())
    assert result.status is BoundsStatus.UNKNOWN_MODEL
    assert plot_bounds_block_message(_A4_PORTRAIT, PlotSettings()) is None


def test_invalid_dimensions() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100mm"/>'
    result = check_plot_bounds(svg, PlotSettings(model=1))
    assert result.status is BoundsStatus.INVALID_DIMENSIONS


def test_portrait_landscape_consistency() -> None:
    ok_landscape = check_plot_bounds(_A4_LANDSCAPE, PlotSettings(model=1))
    ok_portrait = check_plot_bounds(_A4_PORTRAIT, PlotSettings(model=1))
    assert ok_landscape.status is BoundsStatus.OK
    assert ok_portrait.status is BoundsStatus.OK
