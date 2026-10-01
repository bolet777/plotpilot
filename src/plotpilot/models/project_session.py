"""Serializable PlotPilot project state (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.print_margins import PrintMargins
from plotpilot.services.preview_work_area import FallbackWorkArea, WorkAreaOrientation


@dataclass(frozen=True, slots=True)
class ProjectSession:
    """State stored in a .plotpilot file (v1)."""

    svg_path: Path
    checked_layer_ids: tuple[str, ...]
    artwork_transform: ArtworkTransform
    plot_settings: PlotSettings
    fallback_work_area: FallbackWorkArea
    fallback_work_area_orientation: WorkAreaOrientation = WorkAreaOrientation.PORTRAIT
    print_margins: PrintMargins = field(default_factory=PrintMargins)
