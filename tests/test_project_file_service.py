"""Project file format and ProjectFileService."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import REORDERING_BASIC, PlotSettings
from plotpilot.models.project_session import ProjectSession
from plotpilot.services.preview_work_area import FallbackWorkArea
from plotpilot.services.project_file_service import (
    FORMAT_ID,
    ProjectFileError,
    ProjectUnsupportedVersionError,
    read_project_file,
    resolve_svg_path,
    serialize_svg_path,
    session_to_document,
    write_project_file,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _sample_session(svg: Path) -> ProjectSession:
    return ProjectSession(
        svg_path=svg,
        checked_layer_ids=("orange", "cyan"),
        artwork_transform=ArtworkTransform(x_mm=-10.5, y_mm=3.0, scale=1.25),
        plot_settings=PlotSettings(
            pen_down_speed=30,
            pen_up_speed=40,
            acceleration=50,
            model=2,
            path_reordering=REORDERING_BASIC,
        ),
        fallback_work_area=FallbackWorkArea.A3,
    )


def test_v1_round_trip(tmp_path: Path) -> None:
    svg = FIXTURES / "three_root_groups.svg"
    project_file = tmp_path / "demo.plotpilot"
    session = _sample_session(svg.resolve())
    write_project_file(project_file, session)
    loaded = read_project_file(project_file)
    assert loaded == session


def test_document_is_versioned_json(tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    project_file = tmp_path / "x.plotpilot"
    write_project_file(project_file, _sample_session(svg.resolve()))
    data = json.loads(project_file.read_text(encoding="utf-8"))
    assert data["format"] == FORMAT_ID
    assert data["version"] == 1


def test_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.plotpilot"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ProjectFileError, match="valid JSON"):
        read_project_file(bad)


def test_wrong_format(tmp_path: Path) -> None:
    bad = tmp_path / "bad.plotpilot"
    bad.write_text(json.dumps({"format": "other", "version": 1}), encoding="utf-8")
    with pytest.raises(ProjectFileError, match="not a PlotPilot project"):
        read_project_file(bad)


def test_unsupported_future_version(tmp_path: Path) -> None:
    future = tmp_path / "future.plotpilot"
    future.write_text(
        json.dumps({"format": FORMAT_ID, "version": 99, "svg": {"path": "x.svg"}}),
        encoding="utf-8",
    )
    with pytest.raises(ProjectUnsupportedVersionError, match="newer version"):
        read_project_file(future)


def test_relative_svg_path_serialization(tmp_path: Path) -> None:
    svg = tmp_path / "design.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    project_file = tmp_path / "proj.plotpilot"
    stored = serialize_svg_path(project_file, svg)
    assert stored == "design.svg"
    doc = session_to_document(_sample_session(svg), project_file=project_file)
    assert doc["svg"]["path"] == "design.svg"


def test_relative_svg_path_resolution(tmp_path: Path) -> None:
    svg = tmp_path / "nested" / "art.svg"
    svg.parent.mkdir(parents=True)
    svg.write_text("<svg></svg>", encoding="utf-8")
    project_file = tmp_path / "nested" / "job.plotpilot"
    resolved = resolve_svg_path(project_file, "art.svg")
    assert resolved == svg.resolve()


def test_absolute_svg_path_when_not_relative(tmp_path: Path) -> None:
    svg = tmp_path / "elsewhere.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    project_file = tmp_path / "sub" / "job.plotpilot"
    project_file.parent.mkdir(parents=True)
    stored = serialize_svg_path(project_file, svg.resolve())
    assert Path(stored).is_absolute()
    assert resolve_svg_path(project_file, stored) == svg.resolve()


def test_plot_settings_and_transform_round_trip(tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    project_file = tmp_path / "settings.plotpilot"
    session = _sample_session(svg.resolve())
    write_project_file(project_file, session)
    loaded = read_project_file(project_file)
    assert loaded.artwork_transform == session.artwork_transform
    assert loaded.plot_settings == session.plot_settings
    assert loaded.fallback_work_area == FallbackWorkArea.A3


def test_fallback_work_area_defaults_to_a4(tmp_path: Path) -> None:
    project_file = tmp_path / "minimal.plotpilot"
    project_file.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(FIXTURES / "simple.svg")},
            }
        ),
        encoding="utf-8",
    )
    loaded = read_project_file(project_file)
    assert loaded.fallback_work_area is FallbackWorkArea.A4


def test_save_does_not_modify_svg(tmp_path: Path) -> None:
    svg = tmp_path / "source.svg"
    original = (FIXTURES / "simple.svg").read_text(encoding="utf-8")
    svg.write_text(original, encoding="utf-8")
    mtime_before = svg.stat().st_mtime_ns
    write_project_file(tmp_path / "p.plotpilot", _sample_session(svg.resolve()))
    assert svg.read_text(encoding="utf-8") == original
    assert svg.stat().st_mtime_ns == mtime_before
