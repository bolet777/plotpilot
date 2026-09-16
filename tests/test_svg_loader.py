"""Unit tests for loading SVG files from disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from plotpilot.models.svg_document import SvgDocument
from plotpilot.services.svg_loader import SvgLoadError, SvgLoadKind, load_svg_from_path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID = FIXTURES / "valid_basic.svg"


def test_load_valid_svg_extracts_path_and_name() -> None:
    doc = load_svg_from_path(VALID)
    assert isinstance(doc, SvgDocument)
    assert doc.path == VALID.resolve()
    assert doc.name == "valid_basic.svg"
    assert "<svg" in doc.raw_text
    assert doc.root.tag.endswith("svg")


def test_load_missing_file() -> None:
    with pytest.raises(SvgLoadError) as exc_info:
        load_svg_from_path(FIXTURES / "does_not_exist.svg")
    assert exc_info.value.kind is SvgLoadKind.MISSING


def test_load_malformed_xml() -> None:
    with pytest.raises(SvgLoadError) as exc_info:
        load_svg_from_path(FIXTURES / "malformed.xml")
    assert exc_info.value.kind is SvgLoadKind.XML


def test_load_non_svg_xml() -> None:
    with pytest.raises(SvgLoadError) as exc_info:
        load_svg_from_path(FIXTURES / "not_svg.xml")
    assert exc_info.value.kind is SvgLoadKind.NOT_SVG


def test_load_invalid_utf8_encoding(tmp_path: Path) -> None:
    bad = tmp_path / "bad.svg"
    bad.write_bytes(b"\xff\xfe<svg/>")
    with pytest.raises(SvgLoadError) as exc_info:
        load_svg_from_path(bad)
    assert exc_info.value.kind is SvgLoadKind.ENCODING


def test_state_preservation_after_failed_load() -> None:
    """Simulate app holding a document, then failing to open another file."""
    current = load_svg_from_path(VALID)
    original_name = current.name

    with pytest.raises(SvgLoadError):
        load_svg_from_path(FIXTURES / "malformed.xml")

    again = load_svg_from_path(VALID)
    assert again.name == original_name
    assert current.path == again.path
