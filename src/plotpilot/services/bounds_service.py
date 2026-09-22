"""Page-level plot bounds preflight (Qt-free)."""

from __future__ import annotations

from plotpilot.models.plot_bounds import BoundsStatus, PlotBoundsCheck
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_model import get_plotter_model_info
from plotpilot.svg.plot_dimensions import PlotDimensionError, parse_physical_size

# Match axidraw_conf bounds_tolerance (0.003 in) for page-fit comparisons.
_PAGE_FIT_TOLERANCE_MM = 0.003 * 25.4


def _effective_page_mm(
    width_mm: float,
    height_mm: float,
    *,
    auto_rotate: bool,
) -> tuple[float, float]:
    """Match axicli default: rotate when height > width."""
    if auto_rotate and height_mm > width_mm:
        return height_mm, width_mm
    return width_mm, height_mm


def _page_fits(page_x_mm: float, page_y_mm: float, max_x_mm: float, max_y_mm: float) -> bool:
    tol = _PAGE_FIT_TOLERANCE_MM
    return page_x_mm <= max_x_mm + tol and page_y_mm <= max_y_mm + tol


def check_plot_bounds(
    svg_text: str,
    plot_settings: PlotSettings,
    *,
    auto_rotate: bool = True,
) -> PlotBoundsCheck:
    """Compare root SVG page size to selected model travel limits."""
    try:
        physical = parse_physical_size(svg_text)
    except PlotDimensionError as exc:
        return PlotBoundsCheck(
            status=BoundsStatus.INVALID_DIMENSIONS,
            document_width_mm=None,
            document_height_mm=None,
            model_width_mm=None,
            model_height_mm=None,
            model_display_name=None,
            message=exc.user_message,
        )

    if plot_settings.model is None:
        doc_line = f"Document: {_fmt_mm(physical.width_mm)} × {_fmt_mm(physical.height_mm)} mm"
        return PlotBoundsCheck(
            status=BoundsStatus.UNKNOWN_MODEL,
            document_width_mm=physical.width_mm,
            document_height_mm=physical.height_mm,
            model_width_mm=None,
            model_height_mm=None,
            model_display_name=None,
            message=(
                f"{doc_line}\n"
                "Model: Default (CLI) — PlotPilot cannot verify bounds; axicli enforces limits."
            ),
        )

    model = get_plotter_model_info(plot_settings.model)
    page_x, page_y = _effective_page_mm(
        physical.width_mm,
        physical.height_mm,
        auto_rotate=auto_rotate,
    )
    fits = _page_fits(page_x, page_y, model.max_width_mm, model.max_height_mm)

    would_fit_rotated = False
    if not fits:
        alt_x, alt_y = physical.height_mm, physical.width_mm
        if (alt_x, alt_y) != (page_x, page_y) and _page_fits(
            alt_x,
            alt_y,
            model.max_width_mm,
            model.max_height_mm,
        ):
            would_fit_rotated = True

    doc_line = f"Document: {_fmt_mm(physical.width_mm)} × {_fmt_mm(physical.height_mm)} mm"
    model_line = (
        f"{model.display_name}: max {_fmt_mm(model.max_width_mm)} × "
        f"{_fmt_mm(model.max_height_mm)} mm"
    )

    if fits:
        return PlotBoundsCheck(
            status=BoundsStatus.OK,
            document_width_mm=physical.width_mm,
            document_height_mm=physical.height_mm,
            model_width_mm=model.max_width_mm,
            model_height_mm=model.max_height_mm,
            model_display_name=model.display_name,
            message=f"{doc_line}\n{model_line}: fits",
        )

    extra = ""
    if would_fit_rotated:
        extra = "\nArtwork would fit if rotated, but automatic rotation is not implemented."

    return PlotBoundsCheck(
        status=BoundsStatus.OUT_OF_BOUNDS,
        document_width_mm=physical.width_mm,
        document_height_mm=physical.height_mm,
        model_width_mm=model.max_width_mm,
        model_height_mm=model.max_height_mm,
        model_display_name=model.display_name,
        message=f"{doc_line}\n{model_line}\nArtwork exceeds selected model.{extra}",
        would_fit_if_rotated=would_fit_rotated,
    )


def plot_bounds_block_message(svg_text: str, plot_settings: PlotSettings) -> str | None:
    """Return a user message when plotting must be blocked, or None if allowed."""
    result = check_plot_bounds(svg_text, plot_settings)
    if result.status is BoundsStatus.INVALID_DIMENSIONS:
        return result.message
    # Page size may exceed the model; viewport clipping trims geometry at plot time.
    return None


def _fmt_mm(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"
