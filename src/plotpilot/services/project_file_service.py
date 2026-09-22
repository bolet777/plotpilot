"""Read and write versioned .plotpilot project JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plotpilot.models.artwork_transform import ArtworkTransform, ArtworkTransformError
from plotpilot.models.plot_settings import PlotSettings, PlotSettingsValidationError
from plotpilot.models.project_session import ProjectSession
from plotpilot.services.preview_work_area import FallbackWorkArea

FORMAT_ID = "plotpilot-project"
SUPPORTED_VERSION = 1


class ProjectFileError(Exception):
    """Base error for project file operations."""

    def __init__(self, user_message: str) -> None:
        self.user_message = user_message
        super().__init__(user_message)


class ProjectUnsupportedVersionError(ProjectFileError):
    """Project file was created by a newer PlotPilot."""


def serialize_svg_path(project_file: Path, svg_path: Path) -> str:
    """Prefer a path relative to the project file directory."""
    resolved_svg = svg_path.resolve()
    project_dir = project_file.resolve().parent
    try:
        return str(resolved_svg.relative_to(project_dir))
    except ValueError:
        return str(resolved_svg)


def resolve_svg_path(project_file: Path, stored_path: str) -> Path:
    """Resolve a stored SVG path against the project file location."""
    raw = Path(stored_path)
    if raw.is_absolute():
        return raw.resolve()
    return (project_file.resolve().parent / raw).resolve()


def session_to_document(
    session: ProjectSession,
    *,
    project_file: Path,
) -> dict[str, Any]:
    project_file = project_file.resolve()
    stored_svg = serialize_svg_path(project_file, session.svg_path)
    settings = session.plot_settings
    return {
        "format": FORMAT_ID,
        "version": SUPPORTED_VERSION,
        "svg": {"path": stored_svg},
        "layers": {"checked_ids": list(session.checked_layer_ids)},
        "artwork_transform": {
            "x_mm": session.artwork_transform.x_mm,
            "y_mm": session.artwork_transform.y_mm,
            "scale": session.artwork_transform.scale,
        },
        "plot_settings": {
            "pen_down_speed": settings.pen_down_speed,
            "pen_up_speed": settings.pen_up_speed,
            "acceleration": settings.acceleration,
            "model": settings.model,
            "path_reordering": settings.path_reordering,
        },
        "preview": {"fallback_work_area": session.fallback_work_area.value},
    }


def write_project_file(project_file: Path, session: ProjectSession) -> None:
    project_file = project_file.resolve()
    project_file.parent.mkdir(parents=True, exist_ok=True)
    payload = session_to_document(session, project_file=project_file)
    text = json.dumps(payload, indent=2, sort_keys=True)
    text = f"{text}\n"
    project_file.write_text(text, encoding="utf-8")


def read_project_file(project_file: Path) -> ProjectSession:
    """Parse and validate a .plotpilot file."""
    project_file = project_file.resolve()
    try:
        raw_text = project_file.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"Could not read project file:\n{project_file}\n\n{exc}"
        raise ProjectFileError(msg) from exc

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ProjectFileError(
            "This file is not valid JSON. It may be corrupted or not a PlotPilot project.",
        ) from exc

    if not isinstance(data, dict):
        raise ProjectFileError("This file is not a PlotPilot project (expected a JSON object).")

    format_id = data.get("format")
    if format_id != FORMAT_ID:
        raise ProjectFileError(
            "This file is not a PlotPilot project (unrecognized format).",
        )

    version = data.get("version")
    if not isinstance(version, int):
        raise ProjectFileError("This PlotPilot project file is missing a valid version number.")
    if version > SUPPORTED_VERSION:
        raise ProjectUnsupportedVersionError(
            "This project was created by a newer version of PlotPilot.",
        )
    if version < SUPPORTED_VERSION:
        raise ProjectFileError(
            f"This PlotPilot project uses unsupported version {version}.",
        )

    svg_block = data.get("svg")
    if not isinstance(svg_block, dict):
        raise ProjectFileError("This PlotPilot project is missing SVG path information.")
    stored_svg = svg_block.get("path")
    if not isinstance(stored_svg, str) or not stored_svg.strip():
        raise ProjectFileError("This PlotPilot project is missing the SVG path.")

    svg_path = resolve_svg_path(project_file, stored_svg)

    layers_block = data.get("layers")
    checked_ids: tuple[str, ...] = ()
    if isinstance(layers_block, dict):
        raw_ids = layers_block.get("checked_ids", [])
        if raw_ids is None:
            raw_ids = []
        if not isinstance(raw_ids, list):
            raise ProjectFileError("Layer information in this project file is invalid.")
        checked_ids = tuple(str(item) for item in raw_ids if isinstance(item, str))

    transform_block = data.get("artwork_transform")
    if transform_block is None:
        artwork_transform = ArtworkTransform.identity()
    elif not isinstance(transform_block, dict):
        raise ProjectFileError("Artwork transform in this project file is invalid.")
    else:
        try:
            artwork_transform = ArtworkTransform(
                x_mm=float(transform_block.get("x_mm", 0.0)),
                y_mm=float(transform_block.get("y_mm", 0.0)),
                scale=float(transform_block.get("scale", 1.0)),
            )
            artwork_transform.validate()
        except (TypeError, ValueError, ArtworkTransformError) as exc:
            raise ProjectFileError("Artwork transform in this project file is invalid.") from exc

    plot_settings = _parse_plot_settings(data.get("plot_settings"))
    fallback = _parse_fallback(data.get("preview"))

    return ProjectSession(
        svg_path=svg_path,
        checked_layer_ids=checked_ids,
        artwork_transform=artwork_transform,
        plot_settings=plot_settings,
        fallback_work_area=fallback,
    )


def unmatched_layer_ids(
    session: ProjectSession,
    available_layer_ids: set[str],
) -> list[str]:
    missing: list[str] = []
    for layer_id in session.checked_layer_ids:
        if layer_id not in available_layer_ids:
            missing.append(layer_id)
    return missing


def _parse_plot_settings(block: object) -> PlotSettings:
    if block is None:
        return PlotSettings()
    if not isinstance(block, dict):
        raise ProjectFileError("Plot settings in this project file are invalid.")
    settings = PlotSettings(
        pen_down_speed=_optional_int(block.get("pen_down_speed")),
        pen_up_speed=_optional_int(block.get("pen_up_speed")),
        acceleration=_optional_int(block.get("acceleration")),
        model=_optional_int(block.get("model")),
        path_reordering=_optional_int(block.get("path_reordering")),
    )
    try:
        settings.validate()
    except PlotSettingsValidationError as exc:
        raise ProjectFileError("Plot settings in this project file are invalid.") from exc
    return settings


def _parse_fallback(block: object) -> FallbackWorkArea:
    if block is None or not isinstance(block, dict):
        return FallbackWorkArea.A4
    raw = block.get("fallback_work_area")
    if raw == FallbackWorkArea.A3.value:
        return FallbackWorkArea.A3
    return FallbackWorkArea.A4


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
