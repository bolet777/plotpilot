"""Resolve plotter work area and mm-space preview layout (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_model import get_plotter_model_info

# ISO 216 portrait page sizes for Default (CLI) preview fallback only.
_FALLBACK_SIZES_MM: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
}


class FallbackWorkArea(StrEnum):
    A4 = "A4"
    A3 = "A3"


@dataclass(frozen=True, slots=True)
class PreviewWorkArea:
    width_mm: float
    height_mm: float
    label: str
    from_fallback: bool


@dataclass(frozen=True, slots=True)
class MmRect:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float


@dataclass(frozen=True, slots=True)
class PhysicalPreviewLayout:
    """Shared mm workspace: SVG page and plotter area both originate at (0, 0)."""

    workspace_width_mm: float
    workspace_height_mm: float
    mm_to_px: float
    workspace_x_px: float
    workspace_y_px: float
    svg_rect_mm: MmRect
    work_area_rect_mm: MmRect


def resolve_preview_work_area(
    plot_settings: PlotSettings,
    *,
    fallback: FallbackWorkArea = FallbackWorkArea.A4,
) -> PreviewWorkArea | None:
    """Return machine work area from model, or ISO fallback when model is Default (CLI)."""
    if plot_settings.model is not None:
        info = get_plotter_model_info(plot_settings.model)
        return PreviewWorkArea(
            width_mm=info.max_width_mm,
            height_mm=info.max_height_mm,
            label=(
                f"{info.display_name} — {_fmt_mm(info.max_width_mm)} × "
                f"{_fmt_mm(info.max_height_mm)} mm"
            ),
            from_fallback=False,
        )

    key = fallback.value
    width_mm, height_mm = _FALLBACK_SIZES_MM[key]
    return PreviewWorkArea(
        width_mm=width_mm,
        height_mm=height_mm,
        label=f"{key} — {_fmt_mm(width_mm)} × {_fmt_mm(height_mm)} mm",
        from_fallback=True,
    )


def preview_work_area_is_ambiguous(plot_settings: PlotSettings) -> bool:
    return plot_settings.model is None


@dataclass(frozen=True, slots=True)
class PlotViewport:
    """Physical clipping rectangle for plot preparation."""

    width_mm: float
    height_mm: float
    label: str
    hardware_verified: bool


def resolve_plot_viewport(
    plot_settings: PlotSettings,
    *,
    fallback: FallbackWorkArea = FallbackWorkArea.A4,
) -> PlotViewport:
    """Machine viewport for geometric clipping (explicit model or user fallback)."""
    preview = resolve_preview_work_area(plot_settings, fallback=fallback)
    if preview is None:
        msg = "Could not resolve plot viewport."
        raise ValueError(msg)
    return PlotViewport(
        width_mm=preview.width_mm,
        height_mm=preview.height_mm,
        label=preview.label,
        hardware_verified=not preview.from_fallback,
    )


def compute_physical_preview_layout(
    svg_width_mm: float,
    svg_height_mm: float,
    work_width_mm: float,
    work_height_mm: float,
    available_width_px: float,
    available_height_px: float,
    *,
    origin_x_px: float = 0.0,
    origin_y_px: float = 0.0,
) -> PhysicalPreviewLayout | None:
    """Fit a mm workspace into available pixels; preserve physical aspect ratios."""
    if (
        svg_width_mm <= 0
        or svg_height_mm <= 0
        or work_width_mm <= 0
        or work_height_mm <= 0
        or available_width_px <= 0
        or available_height_px <= 0
    ):
        return None

    workspace_w = max(svg_width_mm, work_width_mm)
    workspace_h = max(svg_height_mm, work_height_mm)
    scale = min(available_width_px / workspace_w, available_height_px / workspace_h)
    screen_w = workspace_w * scale
    screen_h = workspace_h * scale
    workspace_x = origin_x_px + (available_width_px - screen_w) / 2
    workspace_y = origin_y_px + (available_height_px - screen_h) / 2

    return PhysicalPreviewLayout(
        workspace_width_mm=workspace_w,
        workspace_height_mm=workspace_h,
        mm_to_px=scale,
        workspace_x_px=workspace_x,
        workspace_y_px=workspace_y,
        svg_rect_mm=MmRect(0.0, 0.0, svg_width_mm, svg_height_mm),
        work_area_rect_mm=MmRect(0.0, 0.0, work_width_mm, work_height_mm),
    )


def mm_rect_to_px(layout: PhysicalPreviewLayout, rect: MmRect) -> tuple[float, float, float, float]:
    scale = layout.mm_to_px
    x = layout.workspace_x_px + rect.x_mm * scale
    y = layout.workspace_y_px + rect.y_mm * scale
    return x, y, rect.width_mm * scale, rect.height_mm * scale


def _fmt_mm(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"
