"""Serializable PlotPilot project state (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.services.preview_work_area import FallbackWorkArea


@dataclass(frozen=True, slots=True)
class ProjectSession:
    """State stored in a .plotpilot file (v1)."""

    svg_path: Path
    checked_layer_ids: tuple[str, ...]
    artwork_transform: ArtworkTransform
    plot_settings: PlotSettings
    fallback_work_area: FallbackWorkArea
